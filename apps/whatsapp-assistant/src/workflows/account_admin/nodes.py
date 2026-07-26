"""Account admin workflow nodes — pure functions, no LangGraph, no I/O, no SQL, no domain rules.

Mirrors workflows/expense_capture/nodes.py's build_draft/request_confirmation
shape. No slot-filling here -- two producers feed this graph's
collected_fields: the deterministic command parser
(runtime/account_admin_parser.py), which always has every field it needs by
construction, and (since 2026-07-26) AI extraction via
SemanticType.ACCOUNT_ADMIN for everything else (other phrasing, voice,
non-English) -- which may resolve `action` but not the action-specific
fields. build_draft's completeness check below handles that gap; duplicate-
name / account-not-found checks still belong to the Application/Domain layer
(see backend's application/finance/resolution.py), not here.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

_MISSING_FIELDS_PROMPT = {
    "create": "What should the new account be called?",
    "rename": "Which account should be renamed, and what should its new name be?",
    "deactivate": "Which account should be deactivated?",
}


def _is_complete(action: str, fields: dict) -> bool:
    if action == "create":
        return bool(str(fields.get("name") or "").strip())
    if action == "rename":
        return bool(str(fields.get("target_name") or "").strip()) and bool(
            str(fields.get("new_name") or "").strip()
        )
    if action == "deactivate":
        return bool(str(fields.get("target_name") or "").strip())
    return False


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction, or -- if the action-specific
    fields AI extraction was supposed to fill in are missing or the action
    itself wasn't recognized -- complete with a clarifying reply and no
    draft at all, mirroring reverse/nodes.py's own "nothing to reverse"
    completeness check (see WorkflowDefinition.allows_completion_without_draft
    in workflows/registry.py, which permits WorkflowKey.ACCOUNT_ADMIN
    to complete without a draft for exactly this case)."""
    fields = dict(state.get("collected_fields") or {})
    action = str(fields.get("action") or "").strip().lower()
    if not _is_complete(action, fields):
        return {
            "pending_prompt": _MISSING_FIELDS_PROMPT.get(
                action, "I didn't catch what you'd like to do with which account."
            )
        }
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
