"""Activity Continuation workflow nodes — pure functions, no LangGraph, no I/O, no SQL.

Appends a Progress Update to an Activity already resolved before this graph
runs (runtime/inbound_journey.py's `_seed_open_activity`, mirroring every
other resolution gate — a node must never query a repository itself). This
graph's only job is: if an activity was found, build the draft and confirm;
if not, say so and end cleanly with no draft (P1: there is nothing here to
append a Progress Update onto, so nothing is persisted).

Field names (`activity_id`, `update_kind`, `narrative`, `quantity`, `unit`)
are exactly what application/progress/mapper.py's
`build_add_progress_update_command` reads out of `confirmed.draft_action.fields`.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

#: Set by _seed_open_activity when no open activity could be found for this
#: reporter/site (runtime/inbound_journey.py). Distinguishes "genuinely
#: nothing to continue" from "seeding simply didn't run" (e.g. a unit test
#: invoking the graph directly) -- the latter should not silently succeed
#: with a missing activity_id.
NO_OPEN_ACTIVITY_FLAG = "no_open_activity"


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction, or end with a clarifying
    message and no draft if no open activity was found to continue."""
    fields = dict(state.get("collected_fields") or {})

    if not fields.get("activity_id"):
        prompt = (
            "I don't see an activity in progress right now to continue. "
            "Want to log this as new work instead? Just describe what was done."
        )
        return {"pending_prompt": prompt, "draft_action": None}

    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=state.get("project_id"),
        site_id=state.get("site_id"),
        fields=fields,
    )
    return {"draft_action": draft}


_UPDATE_KIND_LABEL: dict[str, str] = {
    "STARTED": "Started",
    "PROGRESS": "Progress update",
    "PAUSED": "Paused",
    "RESUMED": "Resumed",
    "COMPLETED": "Completed",
    "NOTE": "Note",
}

_DISPLAY_HIDDEN_FIELD_KEYS = frozenset(
    {
        "activity_id",
        "update_kind",
        "quantity",
        "unit",
        "unit_id",
        "narrative",
        "activity_summary",
        "occurred_at",
        "occurred_date_source",
        "source",
    }
)


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Compose the confirmation prompt — the gate nothing is persisted before
    (principle P2). Mirrors workflows/site_update/nodes.py's shape."""
    draft: DraftActionV2 = state["draft_action"]
    fields = draft.fields

    kind = str(fields.get("update_kind") or "PROGRESS").upper()
    label = _UPDATE_KIND_LABEL.get(kind, "Progress update")

    out = ["*Confirm this update?*", "", f"🏗️ {label}"]

    activity_summary = fields.get("activity_summary")
    if activity_summary:
        out.append(f"   • Activity: {activity_summary}")

    narrative = fields.get("narrative")
    if narrative:
        out.append("")
        out.append(f'   "{narrative}"')

    quantity = fields.get("quantity")
    unit = fields.get("unit")
    if quantity is not None and unit:
        out.append("")
        out.append(f"   • {quantity} {unit}")

    for key, value in fields.items():
        if key in _DISPLAY_HIDDEN_FIELD_KEYS:
            continue
        out.append(f"   • {key}: {value}")

    out.append("")
    out.append("Reply YES to confirm or NO to cancel.")
    return {"pending_prompt": "\n".join(out)}
