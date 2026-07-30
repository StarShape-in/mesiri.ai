"""Add-project-member workflow nodes — pure functions, no LangGraph, no I/O, no SQL.

Mirrors workflows/site_create/nodes.py's build_draft/request_confirmation
shape, with one addition: which project the member is added to comes from
`state["project_id"]`, resolved by the ordinary context pipeline the same
way every other project-scoped workflow already relies on, never from
`collected_fields`. If that resolution came up empty, build_draft asks
instead of building a draft with no project, mirroring site_create's own
missing-project check.

`member_name` is only a best-effort hint at this point -- turning it into a
real user_id is a DB round trip (application/projects/name_resolution.py),
which cannot happen in a pure node (workflows/runtime.py's rule); it travels
untouched on the draft and is resolved by the backend Handler right before
persist, exactly as automation_setup's audience_names are (see
application/automations/handlers.py).

`role` is normalized here (pure string matching, no I/O) into the same
closed vocabulary users.role/project_members.role already use, defaulting
to SITE_ENGINEER -- the same default project_members.role's own column
default applies when nothing is added via the dashboard either.
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

_MISSING_PROJECT_PROMPT = "Which project should I add this member to?"
_MISSING_NAME_PROMPT = "Who should I add to this project?"

_DEFAULT_ROLE = "SITE_ENGINEER"

# Longest/most-specific phrase first within each entry so "project manager"
# doesn't get caught by a looser "manager" alias also meaning PROJECT_MANAGER
# (harmless here since both map the same, but keeps the intent obvious).
_ROLE_ALIASES: tuple[tuple[str, str], ...] = (
    ("project manager", "PROJECT_MANAGER"),
    ("site engineer", "SITE_ENGINEER"),
    ("engineer", "SITE_ENGINEER"),
    ("finance", "FINANCE"),
    ("admin", "ADMIN"),
    ("manager", "PROJECT_MANAGER"),
)

_KNOWN_ROLES = frozenset({"ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"})


def _normalize_role(role_hint: object) -> str:
    """Best-effort mapping of a free-text role hint to the closed role
    vocabulary. Falls back to the default rather than rejecting an
    unrecognized word -- an unmatched role hint ("supervisor") is far more
    likely to mean "give them the standard access" than "abort the whole
    add"."""
    text = str(role_hint or "").strip().upper()
    if text in _KNOWN_ROLES:
        return text
    lowered = text.lower()
    for phrase, role in _ROLE_ALIASES:
        if phrase in lowered:
            return role
    return _DEFAULT_ROLE


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields + the context-resolved project into a
    DraftAction, or -- if the project isn't resolved or AI extraction never
    filled in a member name -- complete with a clarifying reply and no draft
    at all (see WorkflowDefinition.allows_completion_without_draft in
    workflows/registry.py, which permits WorkflowKey.ADD_PROJECT_MEMBER to
    complete without a draft for exactly this case)."""
    project_id = state.get("project_id")
    if not project_id:
        return {"pending_prompt": _MISSING_PROJECT_PROMPT}
    fields = dict(state.get("collected_fields") or {})
    member_name = str(fields.get("member_name") or "").strip()
    if not member_name:
        return {"pending_prompt": _MISSING_NAME_PROMPT}
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.ADD_PROJECT_MEMBER,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=project_id,
        site_id=None,
        fields={
            "member_name": member_name,
            "role": _normalize_role(fields.get("role")),
            "created_by_role": fields.get("created_by_role"),
        },
    )
    return {"draft_action": draft}


_ROLE_DISPLAY = {
    "ADMIN": "Admin",
    "PROJECT_MANAGER": "Project Manager",
    "SITE_ENGINEER": "Site Engineer",
    "FINANCE": "Finance",
}


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Compose the confirmation prompt. Deterministic formatting only — no
    localization/templates/AI generation here (see workflows/material/nodes.py)."""
    draft: DraftActionV2 = state["draft_action"]
    member_name = draft.fields.get("member_name")
    role = _ROLE_DISPLAY.get(str(draft.fields.get("role") or ""), "Site Engineer")
    lines = [
        "*Confirm this action?*",
        "",
        f"👤 Add *{member_name}* to this project as *{role}*",
        "",
        "Reply YES to confirm or NO to cancel.",
    ]
    return {"pending_prompt": "\n".join(lines)}
