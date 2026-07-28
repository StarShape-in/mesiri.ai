"""Site Issue Close-out workflow nodes — pure functions, no LangGraph, no I/O, no SQL, no domain rules.

Mirrors workflows/reverse/nodes.py: no slot-filling -- runtime/inbound_
journey.py's seeding step (_seed_site_issue_close_target) already resolved
"the most recently reported issue in the right status" into a concrete
site_issue_id before this graph ever runs (a node must never query a
repository itself, see workflows/runtime.py's docstring).

Unlike site_issue_report (which always produces a draft), there is a
genuine "nothing to close" outcome here, same as Reverse: when the seeding
step found no matching issue, build_draft deliberately omits draft_action
and returns a friendly pending_prompt instead --
WorkflowDefinition.allows_completion_without_draft in workflows/registry.py
allows WorkflowKey.SITE_ISSUE_CLOSE to complete without a draft for exactly
this case.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

# Seeded alongside site_issue_id purely for the confirmation prompt below --
# real DB reads (runtime/site_issue_query.py via _seed_site_issue_close_target),
# never an unresolved AI hint, so nothing here needs re-resolving. Excluded
# from draft.fields the same way reverse/nodes.py excludes its own seeded
# display-only fields (reversal_amount, reversal_description, etc.).
_INTERNAL_FIELD_KEYS = frozenset(
    {"site_issue_type", "site_issue_severity", "site_issue_narrative"}
)

_ACTION_LABEL: dict[str, str] = {
    "acknowledge": "👀 Acknowledge Issue",
    "resolve": "✅ Resolve Issue",
    "wont_fix": "🚫 Mark Won't Fix",
}

_NOTHING_TO_CLOSE: dict[str, str] = {
    "acknowledge": "You have no open site issues to acknowledge.",
    "resolve": "You have no open or acknowledged site issues to resolve.",
    "wont_fix": "You have no open or acknowledged site issues to mark won't fix.",
}


def build_draft(state: WorkflowGraphState) -> dict:
    """Map already-resolved fields into a DraftAction, or -- if nothing was
    found to close -- complete with a friendly reply and no draft at all."""
    fields = dict(state.get("collected_fields") or {})
    action = str(fields.get("action", "")).strip().lower()
    has_target = bool(fields.get("site_issue_id"))

    if not has_target:
        return {"pending_prompt": _NOTHING_TO_CLOSE.get(action, "Nothing found to update.")}

    draft_fields = {key: value for key, value in fields.items() if key not in _INTERNAL_FIELD_KEYS}
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.CLOSE_SITE_ISSUE,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=state.get("project_id"),
        site_id=state.get("site_id"),
        fields=draft_fields,
    )
    return {"draft_action": draft}


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Deterministic formatting only, using the display fields seeded
    alongside the resolved target (still in collected_fields at this point,
    even though build_draft excluded them from draft.fields)."""
    all_fields = state.get("collected_fields") or {}
    action = str(all_fields.get("action", "")).strip().lower()
    label = _ACTION_LABEL.get(action, "Update Site Issue")
    issue_type = all_fields.get("site_issue_type") or "Issue"
    narrative = all_fields.get("site_issue_narrative")
    notes = all_fields.get("resolution_notes")

    lines = ["*Confirm this update?*", "", label, f"   • Type: {issue_type}"]
    if narrative:
        lines.append(f"   • {narrative}")
    if notes:
        lines.append(f"   • Notes: {notes}")
    lines.append("")
    lines.append("Reply YES to confirm or NO to cancel.")
    return {"pending_prompt": "\n".join(lines)}
