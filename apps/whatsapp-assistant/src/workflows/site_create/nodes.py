"""Site create workflow nodes — pure functions, no LangGraph, no I/O, no SQL.

Mirrors workflows/project_create/nodes.py's build_draft/request_confirmation
shape, with one addition: which project the new site belongs to comes from
`state["project_id"]`, resolved by the ordinary context pipeline
(context/resolver.py -- explicit "at project X" mention, active/workflow
context, or the single-authorized-project default) the same way every other
project/site-scoped workflow (site_issue_report, site_update, ...) already
relies on it, never from `collected_fields`. If that resolution came up
empty (the sender belongs to more than one project and didn't name one),
build_draft asks instead of building a draft with no project, mirroring its
own missing-name check. No I/O here to resolve a project's display name for
the confirmation prompt (nodes are pure) -- the prompt shows the new site's
own fields only, same restraint project_create/nodes.py takes.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

_MISSING_PROJECT_PROMPT = "Which project should I add this site to?"
_MISSING_NAME_PROMPT = "What should the new site be called?"


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields + the context-resolved project into a
    DraftAction, or -- if the project isn't resolved or AI extraction never
    filled in a site name -- complete with a clarifying reply and no draft
    at all (see WorkflowDefinition.allows_completion_without_draft in
    workflows/registry.py, which permits WorkflowKey.SITE_CREATE to
    complete without a draft for exactly this case)."""
    project_id = state.get("project_id")
    if not project_id:
        return {"pending_prompt": _MISSING_PROJECT_PROMPT}
    fields = dict(state.get("collected_fields") or {})
    if not str(fields.get("name") or "").strip():
        return {"pending_prompt": _MISSING_NAME_PROMPT}
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.CREATE_SITE,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=project_id,
        site_id=None,
        fields=fields,
    )
    return {"draft_action": draft}


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Compose the confirmation prompt. Deterministic formatting only — no
    localization/templates/AI generation here (see workflows/material/nodes.py)."""
    draft: DraftActionV2 = state["draft_action"]
    name = draft.fields.get("name")
    location = draft.fields.get("location")
    lines = ["*Confirm this action?*", "", f"🏢 Create a new site: *{name}*"]
    if location:
        lines.append(f"📍 Location: {location}")
    lines.extend(["", "Reply YES to confirm or NO to cancel."])
    return {"pending_prompt": "\n".join(lines)}
