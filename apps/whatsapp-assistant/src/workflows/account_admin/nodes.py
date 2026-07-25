"""Account admin workflow nodes — pure functions, no LangGraph, no I/O, no SQL, no domain rules.

Mirrors workflows/expense_capture/nodes.py's build_draft/request_confirmation
shape. No slot-filling here -- the deterministic command parser
(runtime/account_admin_parser.py) already extracted every field
(action/name/target_name/new_name) before this graph ever runs; duplicate-
name / account-not-found checks belong to the Application/Domain layer (see
backend's application/finance/resolution.py), not here.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction. Shape-mapping only — no validation."""
    fields = dict(state.get("collected_fields") or {})
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.MANAGE_MONEY_ACCOUNT,
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
    action = draft.fields.get("action")
    if action == "create":
        summary = f"Create a new account: *{draft.fields.get('name')}*"
    elif action == "rename":
        summary = f"Rename *{draft.fields.get('target_name')}* to *{draft.fields.get('new_name')}*"
    elif action == "deactivate":
        summary = f"Deactivate account: *{draft.fields.get('target_name')}*"
    else:
        summary = "Unrecognized account action"
    lines = [
        "*Confirm this action?*",
        "",
        f"🏦 {summary}",
        "",
        "Reply YES to confirm or NO to cancel.",
    ]
    return {"pending_prompt": "\n".join(lines)}
