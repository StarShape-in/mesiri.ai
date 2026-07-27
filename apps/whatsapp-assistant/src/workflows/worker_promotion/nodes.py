"""Worker promotion workflow nodes — pure functions, no I/O, no SQL, no LangGraph.

The optional step *after* attendance is already recorded: offer to add the
newly-seen named temporary workers to the permanent Worker Register. It never
runs before attendance is saved, and never blocks or slows it (plan
principles P1 + P9 — record fast, manage the register later).

The single re-entrant node ``offer_and_promote`` handles up to three passes:

Pass 1 (no slot filled):
    List the named temporary workers and ask which to add. Answers are given
    **by name**, not by list number -- on a 15-worker report, numbers are
    unreadable on a phone and easy to mis-key.

Pass 2 (``promotion_choice`` answered):
    Resolve the chosen names, then run the duplicate check: score each
    against the existing register on name + trade + contractor (the same
    domain scorer attendance matching uses). Anyone with no likely match is
    created immediately. Anyone who *does* look like an existing worker is
    held back for one confirming question rather than silently creating a
    second record for the same person.

Pass 3 (``promotion_duplicate_check`` answered, only when pass 2 held someone):
    Whoever the user says is genuinely a different person gets created; the
    rest are left alone, already being in the register.

**I/O isolation.** The ``create_worker`` DB call and the register snapshot
are both *seeded* into the state by the caller (runtime/inbound_journey.py),
the same pattern that worker candidates are seeded for ``match_workers`` in
the labour_update workflow. This keeps the node free of repository imports
and therefore trivially testable with a fake callable.
"""

from __future__ import annotations

from typing import Any

from mesiri.domains.workforce.matching import (
    ReportedWorker,
    WorkerCandidate,
    score_candidate,
)
from mesiri.domains.workforce.workers import normalize_name

from ..state import WorkflowGraphState

#: Slot holding "which of these workers should I add?".
PROMOTION_SLOT = "promotion_choice"
#: Slot holding "which of these are actually different people?".
DUPLICATE_SLOT = "promotion_duplicate_check"

#: Any register entry scoring at or above this is worth one question before a
#: new permanent worker is created.
#:
#: Deliberately lower than matching.ASK, which governs the *attendance* path.
#: There, a question costs the supervisor time mid-report, so the threshold is
#: set to keep interruptions rare (P9). Here attendance is already saved and
#: the entire purpose of the step is to avoid a duplicate register entry, so
#: the trade-off inverts: asking is nearly free, and a wrong silent write is
#: permanent. At 0.20 this catches the case ASK misses -- a partial name whose
#: score was pulled under ASK by a trade mismatch ("Ajith, painter" against
#: registered "Ajith Kumar, mason"), which is a trade change at least as often
#: as it is a second person. Below it there is no name overlap at all, and
#: trade or contractor alone must never suggest a specific person (P4).
_DUPLICATE_SUSPICION = 0.20

_NONE_WORDS = frozenset(
    {"none", "no", "skip", "no thanks", "nope", "cancel", "later", "not now"}
)
_ALL_WORDS = frozenset({"all", "yes", "all of them", "add all", "yes all", "everyone"})


# --- Helpers -----------------------------------------------------------------


def _promotable(fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Named temporary workers the caller seeded for this workflow."""
    raw = fields.get("promotable_workers")
    if not isinstance(raw, list):
        return []
    return [w for w in raw if isinstance(w, dict) and str(w.get("name") or "").strip()]


def _pretty_trade(trade: str | None) -> str:
    return (trade or "").replace("_", " ").strip().title()


def _describe(worker: dict[str, Any]) -> str:
    trade = _pretty_trade(worker.get("trade"))
    return f"{worker['name']} – {trade}" if trade else str(worker["name"])


def _example_names(workers: list[dict[str, Any]]) -> str:
    """A worked example built from the names actually on screen, so the reply
    format is unambiguous without generalising from placeholders."""
    names = [str(w["name"]) for w in workers]
    return ", ".join(names[:2]) if len(names) > 1 else names[0]


def _build_offer_message(workers: list[dict[str, Any]]) -> str:
    lines = [
        "Attendance recorded successfully.",
        "",
        "Would you like to add any of these workers to your permanent Worker Register?",
        "",
    ]
    lines.extend(f"• {_describe(w)}" for w in workers)
    lines.extend(
        [
            "",
            "Reply with:",
            "• all",
            "• none",
            f"• or the names (e.g. {_example_names(workers)})",
        ]
    )
    return "\n".join(lines)


def _select_by_name(text: str, workers: list[dict[str, Any]]) -> list[int] | None:
    """Resolve a free-text reply to indices into ``workers``.

    Accepts "all", "none", or any list of names in any separator style
    ("Ajith, Rahul" / "Ajith and Rahul" / "ajith rahul"). Matching is on
    normalized names; a reply naming nobody recognisable returns None so the
    question is re-asked rather than silently doing nothing.
    """
    stripped = " ".join(text.strip().lower().split())
    if not stripped:
        return None
    if stripped in _ALL_WORDS:
        return list(range(len(workers)))
    if stripped in _NONE_WORDS:
        return []

    normalized_reply = normalize_name(text)
    if not normalized_reply:
        return None
    reply_tokens = set(normalized_reply.split())

    chosen: list[int] = []
    for i, worker in enumerate(workers):
        worker_name = normalize_name(str(worker["name"]))
        if not worker_name:
            continue
        # The whole name as a phrase ("ravi kumar"), or every token of it
        # present somewhere in the reply.
        if worker_name in normalized_reply or set(worker_name.split()) <= reply_tokens:
            chosen.append(i)

    return chosen or None


def _as_candidates(register: list[Any]) -> list[WorkerCandidate]:
    out: list[WorkerCandidate] = []
    for row in register:
        if not isinstance(row, dict) or not row.get("worker_id"):
            continue
        out.append(
            WorkerCandidate(
                worker_id=str(row["worker_id"]),
                name=str(row.get("name") or ""),
                trade=row.get("trade"),
                contractor=row.get("contractor"),
            )
        )
    return out


def _likely_existing(worker: dict[str, Any], register: list[WorkerCandidate]) -> str | None:
    """The name of an existing register entry this worker probably already is.

    Scores with the shared domain scorer on name + trade + contractor, against
    _DUPLICATE_SUSPICION rather than match_worker's attendance-tuned bands.
    Deliberately passes no site/project history: this asks "is this person
    already in the register?", which has nothing to do with where they have
    worked.
    """
    if not register:
        return None
    reported = ReportedWorker(
        name=str(worker["name"]),
        trade=worker.get("trade"),
        contractor=worker.get("contractor"),
    )
    best = max(
        (score_candidate(reported, c) for c in register),
        key=lambda s: s.confidence,
        default=None,
    )
    if best is None or best.confidence < _DUPLICATE_SUSPICION:
        return None
    return best.name


def _build_duplicate_message(held: list[dict[str, Any]]) -> str:
    def _line(worker: dict[str, Any]) -> str:
        # Parenthesised trade here rather than the offer list's "Name – Trade":
        # this line already carries a dash before "similar to", and two dashes
        # in one line read as a single run-on.
        trade = _pretty_trade(worker.get("trade"))
        who = f"{worker['name']} ({trade})" if trade else str(worker["name"])
        return f"• {who} — similar to {worker['_similar_to']}"

    lines = ["I found similar workers already in your register:", ""]
    lines.extend(_line(w) for w in held)
    lines.extend(
        [
            "",
            "Are any of these actually different people?",
            "",
            "Reply with their names to add them as new workers, or none if they "
            "are already registered.",
        ]
    )
    return "\n".join(lines)


def _create_selected(
    workers: list[dict[str, Any]], fields: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Run the seeded create callable over ``workers``. Returns (created, failed)."""
    create_fn = fields.get("_create_worker_fn")
    created: list[str] = []
    failed: list[str] = []
    for worker in workers:
        if create_fn is None:
            failed.append(str(worker["name"]))
            continue
        try:
            create_fn(
                name=str(worker["name"]),
                trade=worker.get("trade"),
                daily_wage=worker.get("daily_wage"),
            )
            created.append(str(worker["name"]))
        except Exception:  # noqa: BLE001 — promotion never disturbs saved attendance
            failed.append(str(worker["name"]))
    return created, failed


def _closing_message(created: list[str], failed: list[str]) -> str:
    parts: list[str] = []
    if created:
        parts.append(f"✅ Added to your Worker Register: {', '.join(created)}")
    if failed:
        parts.append(
            f"⚠️ Could not add: {', '.join(failed)} — please add them from the dashboard."
        )
    if not parts:
        parts.append(
            "No problem — they stay as temporary workers. You can add them any "
            "time from the Worker Register on the dashboard."
        )
    return "\n".join(parts)


def _ask(prompt: str, slot: str, fields: dict[str, Any]) -> dict:
    return {"collected_fields": fields, "awaiting_slot": slot, "pending_prompt": prompt}


def _done(prompt: str, fields: dict[str, Any]) -> dict:
    return {"collected_fields": fields, "awaiting_slot": None, "pending_prompt": prompt}


# --- Node --------------------------------------------------------------------


def offer_and_promote(state: WorkflowGraphState) -> dict:
    """Re-entrant node — see module docstring for the three-pass semantics."""
    fields = dict(state.get("collected_fields") or {})
    workers = _promotable(fields)

    # Guard: only ever reached via inbound_journey's direct instantiation, and
    # only when it found named temps. An empty list means the caller made a
    # mistake -- complete neutrally rather than sending an empty offer.
    if not workers:
        return {"collected_fields": fields, "awaiting_slot": None, "pending_prompt": None}

    answer = fields.pop("_slot_answer_text", None)
    awaiting = state.get("awaiting_slot")
    register = _as_candidates(fields.get("_register") or [])

    # --- Pass 3: which of the look-alikes are genuinely new people? ----------
    if awaiting == DUPLICATE_SLOT and answer is not None:
        held: list[dict[str, Any]] = list(fields.get("_held_for_duplicate_check") or [])
        selection = _select_by_name(answer, held)
        if selection is None:
            return _ask(
                "Sorry, I didn't catch that.\nReply with the names of anyone who is "
                "a different person, or none.",
                DUPLICATE_SLOT,
                fields,
            )

        created, failed = _create_selected([held[i] for i in selection], fields)
        return _done(
            _closing_message(
                list(fields.get("_created_so_far") or []) + created,
                list(fields.get("_failed_so_far") or []) + failed,
            ),
            fields,
        )

    # --- Pass 2: resolve the chosen names, then screen for duplicates --------
    if awaiting == PROMOTION_SLOT and answer is not None:
        selection = _select_by_name(answer, workers)
        if selection is None:
            return _ask(
                "Sorry, I didn't catch that.\nReply with all, none, or the names of "
                "the workers to add.",
                PROMOTION_SLOT,
                fields,
            )
        if not selection:
            return _done(_closing_message([], []), fields)

        clear: list[dict[str, Any]] = []
        held: list[dict[str, Any]] = []
        for i in selection:
            worker = workers[i]
            similar = _likely_existing(worker, register)
            if similar:
                held.append({**worker, "_similar_to": similar})
            else:
                clear.append(worker)

        created, failed = _create_selected(clear, fields)

        if held:
            fields["_held_for_duplicate_check"] = held
            # Carried so the run ends with one closing summary covering both
            # halves, rather than two partial ones.
            fields["_created_so_far"] = created
            fields["_failed_so_far"] = failed
            return _ask(_build_duplicate_message(held), DUPLICATE_SLOT, fields)

        return _done(_closing_message(created, failed), fields)

    # --- Pass 1: the offer ---------------------------------------------------
    return _ask(_build_offer_message(workers), PROMOTION_SLOT, fields)
