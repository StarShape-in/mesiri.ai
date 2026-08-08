"""Pure structural validation for CreateAutomationCommand -- no DB, no I/O.

Mirrors domains/automations/router.py's AutomationRequest.model_validator
exactly (same field-shape rules), plus the role gate, so a chat-created
automation is held to the identical bar as a dashboard-created one. Name->
user-id resolution (audience_names -> audience_user_ids) is NOT done here --
that needs a DB round trip and happens in name_resolution.py, run by the
Handler before this validate() is called (mirrors
application/projects/create_site_validation.py's split between structural
checks here and the DB-backed existence re-check in the execution
repository).
"""

from __future__ import annotations

from .create_commands import CreateAutomationCommand
from .scheduling import parse_time_of_day

_VALID_ACTIONS = {"SEND_DPR", "COMPLIANCE_SUMMARY", "REMINDER"}
_VALID_AUDIENCES = {"SELF", "USERS", "ROLE", "NON_REPORTERS"}
_VALID_FREQUENCIES = {"DAILY", "WEEKDAYS", "WEEKLY"}
# Matches domains/automations/router.py's _TARGET_OTHERS_ROLES exactly --
# same roles that may target a Project/Site create at someone else may
# target an automation at anyone other than themselves.
_TARGET_OTHERS_ROLES = frozenset({"ADMIN", "PROJECT_MANAGER"})


def validate(cmd: CreateAutomationCommand) -> list[str]:
    reasons: list[str] = []

    if cmd.action not in _VALID_ACTIONS:
        reasons.append(f"'{cmd.action}' is not a recognised automation action")
    if cmd.audience not in _VALID_AUDIENCES:
        reasons.append(f"'{cmd.audience}' is not a recognised audience")
    if cmd.frequency not in _VALID_FREQUENCIES:
        reasons.append(f"'{cmd.frequency}' is not a recognised frequency")

    if cmd.audience != "SELF" and str(cmd.created_by_role or "").strip().upper() not in (
        _TARGET_OTHERS_ROLES
    ):
        reasons.append("only an admin or project manager can target an automation at other people")

    if cmd.audience == "USERS" and not (cmd.audience_user_ids or cmd.audience_names):
        reasons.append("audience_user_ids or audience_names is required when audience is USERS")
    if cmd.audience == "ROLE" and not (cmd.audience_role or "").strip():
        reasons.append("audience_role is required when audience is ROLE")
    if cmd.action == "REMINDER" and not (cmd.message or "").strip():
        reasons.append("message is required when action is REMINDER")
    if cmd.action == "SEND_DPR" and not cmd.site_id:
        reasons.append("a site is required to send a DPR (a DPR is site-scoped)")
    if cmd.frequency == "WEEKLY" and cmd.day_of_week is None:
        reasons.append("day_of_week is required when frequency is WEEKLY")
    if cmd.day_of_week is not None and not (0 <= cmd.day_of_week <= 6):
        reasons.append("day_of_week must be 0 (Monday) through 6 (Sunday)")

    try:
        parse_time_of_day(cmd.time_of_day)
    except (ValueError, IndexError, TypeError):
        reasons.append('time_of_day must be "HH:MM"')

    return reasons
