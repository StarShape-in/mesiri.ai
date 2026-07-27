"""Worker promotion workflow nodes — pure functions, no I/O, no SQL, no LangGraph.

The single re-entrant node ``offer_and_promote`` handles both passes:

Pass 1 (``promotion_choice`` slot not yet filled):
    Build the numbered list of new named temporary workers, attach "All" and
    "None" quick-action options, and pause as COLLECTING_FIELDS.

Pass 2 (slot filled with the user's answer):
    Parse the selection (numbers, "all", "none", any mix) from the answer,
    then for each selected worker call the DB write function that was seeded
    into ``collected_fields["_create_worker_fn"]`` by inbound_journey.py.
    Returns a short confirmation and completes.

**I/O isolation.** The actual ``create_worker`` DB call is *seeded* into the
state by the caller (inbound_journey.py), the same pattern that worker
candidates are seeded for ``match_workers`` in the labour_update workflow.
This keeps the node free of repository imports and therefore trivially
testable with a fake callable.

**Duplicate guard.** Before each DB write the seeded ``_existing_worker_ids``
set (also seeded by the caller from the same candidate list already in memory)
is checked. A worker_id that already exists is skipped silently — the
attendance line already holds the correct worker_id, nothing to do.
"""

from __future__ import annotations

import re
from typing import Any

from ..slots import SlotCandidate, slot_options
from ..state import WorkflowGraphState

#: Slot name used to park the user's choice between passes.
PROMOTION_SLOT = "promotion_choice"

#: Sentinel value for the "All" quick-action tap.
_ALL_SENTINEL = "__all__"
#: Sentinel value for the "None / skip" quick-action tap.
_NONE_SENTINEL = "__none__"


# --- Helpers -----------------------------------------------------------------


def _promotable(fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Named temporary workers the caller seeded for this workflow."""
    raw = fields.get("promotable_workers")
    if not isinstance(raw, list):
        return []
    return [w for w in raw if isinstance(w, dict) and w.get("name")]


def _build_offer_message(workers: list[dict[str, Any]]) -> str:
    """The follow-up message sent after attendance is confirmed."""
    lines: list[str] = [
        "I found these new named workers:",
        "",
    ]
    for i, w in enumerate(workers, start=1):
        trade_hint = f" ({w['trade'].replace('_', ' ')})" if w.get("trade") else ""
        lines.append(f"{i}. {w['name']}{trade_hint}")

    lines.extend([
        "",
        "They have all been recorded as temporary workers for today's attendance.",
        "",
        "Would you like to add any of them to your Worker Register?",
        "",
        "Reply with numbers separated by commas or spaces (e.g. 1, 3 or 1 2 4),",
        "or tap All to add everyone, None to skip.",
    ])
    return "\n".join(lines)


def _parse_selection(text: str, count: int) -> set[int] | None:
    """Parse the user's reply into a set of 0-based indices.

    Accepts:
    - "all" / "All" / any case → all indices
    - "none" / "skip" / any case → empty set
    - Any combination of numbers: "5", "5,7", "5 7", "1,3,5", "2 4 8"
    - Numbers out of range are silently dropped; if every number was
      out of range (e.g. "99") we return None to re-ask.

    Returns None when the reply is unintelligible (re-ask the question).
    """
    stripped = text.strip().lower()
    if not stripped:
        return None
    if stripped in ("all", "yes all", "add all", "all of them"):
        return set(range(count))
    if stripped in ("none", "no", "skip", "no thanks", "nope", "cancel"):
        return set()

    # Extract every integer token from the reply (handles commas, spaces, slashes)
    tokens = re.findall(r"\d+", stripped)
    if not tokens:
        return None
    indices: set[int] = set()
    for tok in tokens:
        idx = int(tok) - 1  # 1-based → 0-based
        if 0 <= idx < count:
            indices.add(idx)
    # If every token was out of range, we can't meaningfully proceed.
    return indices if indices else None


def _quick_action_options() -> list[SlotCandidate]:
    """The two WhatsApp quick-action buttons sent with the offer."""
    return [
        SlotCandidate(value=_ALL_SENTINEL, label="All"),
        SlotCandidate(value=_NONE_SENTINEL, label="None"),
    ]


# --- Node --------------------------------------------------------------------


def offer_and_promote(state: WorkflowGraphState) -> dict:
    """Re-entrant node — see module docstring for two-pass semantics."""
    fields = dict(state.get("collected_fields") or {})
    workers = _promotable(fields)

    # Assertion guard: this workflow must only be reached via inbound_journey's
    # direct instantiation, never via AI planner intent. An empty list means
    # the caller made a mistake — bail with a neutral completion.
    if not workers:
        return {
            "collected_fields": fields,
            "awaiting_slot": None,
            "pending_prompt": None,
        }

    answer_text: str | None = fields.pop("_slot_answer_text", None)

    # --- Pass 2: process the answer ------------------------------------------
    if state.get("awaiting_slot") == PROMOTION_SLOT and answer_text is not None:
        # Quick-action taps come back as the label text.
        label_lower = answer_text.strip().lower()
        if label_lower == "all":
            selection: set[int] | None = set(range(len(workers)))
        elif label_lower in ("none", "skip"):
            selection = set()
        else:
            selection = _parse_selection(answer_text, len(workers))

        if selection is None:
            # Unintelligible reply — re-ask.
            prompt = (
                "Sorry, I didn't catch that.\n"
                "Please reply with numbers (e.g. 1, 3) or tap All / None."
            )
            return {
                "collected_fields": fields,
                "awaiting_slot": PROMOTION_SLOT,
                "awaiting_slot_options": slot_options(_quick_action_options()),
                "pending_prompt": prompt,
            }

        created: list[str] = []
        skipped: list[str] = []

        if selection:
            create_fn = fields.get("_create_worker_fn")
            existing_ids: set[str] = set(fields.get("_existing_worker_ids") or [])

            for idx in sorted(selection):
                if idx >= len(workers):
                    continue
                w = workers[idx]
                existing_id = w.get("matched_worker_id")
                if existing_id and existing_id in existing_ids:
                    # Final duplicate guard: already in the register.
                    skipped.append(w["name"])
                    continue
                if create_fn is not None:
                    try:
                        # Async: the graph node is called via ainvoke, so we
                        # cannot await here. inbound_journey.py wraps the
                        # create_worker coroutine in a synchronous shim
                        # (see _sync_create_worker in inbound_journey.py) so
                        # this call is safe inside a LangGraph sync node.
                        create_fn(
                            name=w["name"],
                            trade=w.get("trade"),
                            daily_wage=w.get("daily_wage"),
                        )
                        created.append(w["name"])
                    except Exception:  # noqa: BLE001 — promotion failure never drops attendance
                        skipped.append(w["name"])
                else:
                    skipped.append(w["name"])

        # Build confirmation message.
        parts: list[str] = []
        if created:
            names = ", ".join(created)
            parts.append(f"✅ Added to your Worker Register: {names}")
        if skipped and selection:
            names = ", ".join(skipped)
            parts.append(f"⚠️ Could not add: {names} — please add them from the dashboard.")
        if not selection:
            parts.append(
                "No problem — they remain as temporary workers. "
                "You can always add them from the Worker Register on the dashboard."
            )
        if selection and not created and not skipped:
            parts.append("Nothing to add.")

        return {
            "collected_fields": fields,
            "awaiting_slot": None,
            "pending_prompt": "\n".join(parts) if parts else "Done.",
        }

    # --- Pass 1: build and send the offer ------------------------------------
    prompt = _build_offer_message(workers)
    return {
        "collected_fields": fields,
        "awaiting_slot": PROMOTION_SLOT,
        "awaiting_slot_options": slot_options(_quick_action_options()),
        "pending_prompt": prompt,
    }
