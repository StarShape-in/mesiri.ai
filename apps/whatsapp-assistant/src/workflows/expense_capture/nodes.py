"""Expense capture workflow nodes — pure functions, no LangGraph, no I/O, no SQL, no domain rules.

Mirrors workflows/material/nodes.py. Each node takes the graph's working
state and returns the partial update LangGraph merges in. Shape-mapping
only — amount>0 and category resolution belong to the Application/Domain
layer (see backend's application/expenses/{validation.py,resolution.py}),
not here.

`resolve_account` is Finance Module Slice 1's "which account?" slot: account
candidates are seeded into `collected_fields['account_candidates']` by the
caller (a node must never query a repository itself -- see
runtime/money_account_query.py and workflows/runtime.py's docstring), and
"my own pocket (reimburse me later)" is always appended as an extra choice
so paying personally is a first-class answer, not merely an omitted account.
See docs/execution/FINANCE_MODULE_PLAN.md's Slice 1.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..slots import SlotCandidate, match_slot_answer, resolve_single_choice_slot
from ..state import WorkflowGraphState

OWN_POCKET_SENTINEL = "own_pocket"
_ACCOUNT_SLOT_NAME = "account_id"
_ACCOUNT_PROMPT_TITLE = "Which account did you pay from?"
_OWN_POCKET_LABEL = "My own pocket (reimburse me later)"


def _account_candidates(raw_candidates: list[dict[str, Any]]) -> list[SlotCandidate]:
    candidates = [SlotCandidate(value=str(c["id"]), label=str(c["name"])) for c in raw_candidates]
    candidates.append(SlotCandidate(value=OWN_POCKET_SENTINEL, label=_OWN_POCKET_LABEL))
    return candidates


def _apply_account_choice(value: str, fields: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(fields)
    if value == OWN_POCKET_SENTINEL:
        resolved["paid_from_own_pocket"] = True
    else:
        resolved["account_id"] = value
    return resolved


def resolve_account(state: WorkflowGraphState) -> dict:
    """Resolve the paid-from choice, asking only when genuinely ambiguous.

    Already resolved (account_id or paid_from_own_pocket already set) ->
    no-op. Otherwise builds the candidate list (real accounts + the always-
    present own-pocket sentinel) and either auto-fills (0 real accounts ->
    own pocket is the only choice), consumes a pending slot answer
    (`_slot_answer_text`, set by WorkflowRuntime.provide_input on resume),
    or asks.
    """
    fields = dict(state.get("collected_fields") or {})
    if fields.get("account_id") is not None or fields.get("paid_from_own_pocket"):
        return {}

    raw_candidates = fields.get("account_candidates") or []
    candidates = _account_candidates(raw_candidates)
    answer_text = fields.pop("_slot_answer_text", None)

    if answer_text is not None:
        matched = match_slot_answer(answer_text, candidates)
        if matched is not None:
            return {"collected_fields": _apply_account_choice(matched, fields), "awaiting_slot": None}
        # No match -- re-ask with the same choices, distinguishing the retry
        # so the user knows their reply wasn't understood rather than
        # silently seeing the identical prompt twice.
        resolution = resolve_single_choice_slot(
            slot_name=_ACCOUNT_SLOT_NAME,
            prompt_title=f"Sorry, I didn't catch that. {_ACCOUNT_PROMPT_TITLE}",
            candidates=candidates,
        )
        return {
            "collected_fields": fields,
            "awaiting_slot": resolution.awaiting_slot,
            "pending_prompt": resolution.slot_prompt,
        }

    resolution = resolve_single_choice_slot(
        slot_name=_ACCOUNT_SLOT_NAME, prompt_title=_ACCOUNT_PROMPT_TITLE, candidates=candidates
    )
    if resolution.resolved_value is not None:
        return {"collected_fields": _apply_account_choice(resolution.resolved_value, fields)}
    return {
        "collected_fields": fields,
        "awaiting_slot": resolution.awaiting_slot,
        "pending_prompt": resolution.slot_prompt,
    }


_INTERNAL_FIELD_KEYS = frozenset({"account_candidates"})


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction. Shape-mapping only — no validation.

    Excludes `account_candidates` -- the seeded candidate list resolve_account
    consumes is plumbing, never a field the user should see echoed back in
    the confirmation prompt or passed on to RecordExpenseCommand.
    """
    fields = {
        key: value
        for key, value in (state.get("collected_fields") or {}).items()
        if key not in _INTERNAL_FIELD_KEYS
    }
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.RECORD_EXPENSE,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=state.get("project_id"),
        site_id=state.get("site_id"),
        fields=fields,
    )
    return {"draft_action": draft}


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Compose the confirmation prompt. Deterministic formatting only — no
    localization/templates/AI generation here (see workflows/material/nodes.py)."""
    draft: DraftActionV2 = state["draft_action"]
    lines = ["*Confirm this record?*", "", "💸 Expense"]
    for key, value in draft.fields.items():
        lines.append(f"   • {key}: {value}")
    lines.append("")
    lines.append("Reply YES to confirm or NO to cancel.")
    return {"pending_prompt": "\n".join(lines)}
