"""Automation setup workflow nodes — pure functions, no LangGraph, no I/O, no SQL.

Mirrors workflows/site_create/nodes.py's build_draft/request_confirmation
shape. The one genuinely new piece of work here is translating what the AI
extraction hands back (see platform/ai/.../adapter.py's `automation_setup`
prompt block: `automation_action`, `audience`, `audience_names`,
`audience_role`, `day_of_week` as an English weekday name) into the shape
`application/automations/create_commands.py`'s CreateAutomationCommand
actually expects (`action`, `audience`, `audience_user_ids`/`audience_names`
carried through as-is, `day_of_week` as 0=Monday..6=Sunday). That is pure
string/int mapping, so it belongs here rather than in the application layer.

`audience_names` -> `audience_user_ids` resolution is NOT done here -- that
needs a DB round trip against the org's real users (see
application/automations/name_resolution.py), and a node must never query a
repository itself (workflows/runtime.py's docstring). `audience_names`
travels through untouched on the draft; the Handler resolves it right before
persist, same "resolve at confirm time" split account_admin/finance already
use for target_name/new_name.

Which project/site this automation is scoped to comes from
`state["project_id"]`/`state["site_id"]`, resolved by the ordinary context
pipeline (context/resolver.py) exactly like every other project/site-scoped
workflow -- never asked for explicitly. Unlike site_create, an unresolved
project_id is NOT fatal here: SELF/USERS/ROLE digests can be entirely
org-wide (project_id stays None), only SEND_DPR truly needs a site (enforced
by create_validation.py, not this node).
"""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState

_MISSING_TIME_PROMPT = (
    "What time should this run? (e.g. \"5pm\", \"15:30\")"
)

_WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_ACTION_LABELS = {
    "SEND_DPR": "send the Daily Progress Report",
    "COMPLIANCE_SUMMARY": "tell you who has/hasn't reported",
    "REMINDER": "send a reminder",
}

_AUDIENCE_LABELS = {
    "SELF": "you",
    "USERS": "the people named",
    "ROLE": "everyone in that role",
    "NON_REPORTERS": "whoever hasn't reported yet",
}

_FREQUENCY_LABELS = {
    "DAILY": "every day",
    "WEEKDAYS": "on weekdays",
    "WEEKLY": "every week",
}


def _normalize_day_of_week(raw: object) -> int | None:
    """Accepts an English weekday name (from AI extraction) or an already-
    numeric value (from a resumed/edited draft) -- never guesses when the
    text doesn't match a real weekday."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if 0 <= raw <= 6 else None
    text = str(raw).strip().lower()
    if text in _WEEKDAY_NAMES:
        return _WEEKDAY_NAMES[text]
    if text.isdigit() and 0 <= int(text) <= 6:
        return int(text)
    return None


def _normalize_fields(raw: dict) -> dict:
    """Map AI-extraction field names/shapes onto what CreateAutomationCommand
    expects, filling in the defaults the plan calls for: frequency defaults
    to DAILY, action defaults to REMINDER when a free-text message was
    given (the sender clearly wants to say something) or SEND_DPR
    otherwise, audience defaults to SELF unless audience_names/audience_role
    imply otherwise."""
    fields = dict(raw)

    action = str(fields.pop("automation_action", "") or fields.get("action") or "").strip().upper()
    message = fields.get("message")
    if action not in _ACTION_LABELS:
        action = "REMINDER" if str(message or "").strip() else "SEND_DPR"
    fields["action"] = action

    audience = str(fields.get("audience") or "").strip().upper()
    if audience not in _AUDIENCE_LABELS:
        if fields.get("audience_names"):
            audience = "USERS"
        elif fields.get("audience_role"):
            audience = "ROLE"
        else:
            audience = "SELF"
    fields["audience"] = audience

    frequency = str(fields.get("frequency") or "").strip().upper()
    if frequency not in _FREQUENCY_LABELS:
        frequency = "DAILY"
    fields["frequency"] = frequency

    day_of_week = _normalize_day_of_week(fields.get("day_of_week"))
    if day_of_week is not None:
        fields["day_of_week"] = day_of_week
    else:
        fields.pop("day_of_week", None)

    return fields


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction, or -- if AI extraction never
    filled in a time -- complete with a clarifying reply and no draft at all
    (see WorkflowDefinition.allows_completion_without_draft in
    workflows/registry.py, which must permit WorkflowKey.AUTOMATION_SETUP to
    complete without a draft for exactly this case, mirroring SITE_CREATE's
    missing-name case)."""
    raw_fields = dict(state.get("collected_fields") or {})
    if not str(raw_fields.get("time_of_day") or "").strip():
        return {"pending_prompt": _MISSING_TIME_PROMPT}

    fields = _normalize_fields(raw_fields)
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.CREATE_AUTOMATION,
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
    fields = draft.fields
    action = str(fields.get("action") or "REMINDER")
    audience = str(fields.get("audience") or "SELF")
    frequency = str(fields.get("frequency") or "DAILY")
    time_of_day = fields.get("time_of_day")

    when = _FREQUENCY_LABELS.get(frequency, "every day")
    if frequency == "WEEKLY" and fields.get("day_of_week") is not None:
        weekday_name = [k for k, v in _WEEKDAY_NAMES.items() if v == fields["day_of_week"]]
        if weekday_name:
            when = f"every {weekday_name[0].capitalize()}"

    who = _AUDIENCE_LABELS.get(audience, "you")
    if audience == "USERS" and fields.get("audience_names"):
        who = ", ".join(str(n) for n in fields["audience_names"])
    elif audience == "ROLE" and fields.get("audience_role"):
        who = f"every {fields['audience_role']}"

    what = _ACTION_LABELS.get(action, "send a reminder")

    lines = [
        "*Confirm this automation?*",
        "",
        f"⏰ At {time_of_day}, {when}",
        f"📋 {what.capitalize()}",
        f"👥 To: {who}",
    ]
    if action == "REMINDER" and fields.get("message"):
        lines.append(f"💬 Message: {fields['message']}")
    lines.extend(["", "Reply YES to confirm or NO to cancel."])
    return {"pending_prompt": "\n".join(lines)}
