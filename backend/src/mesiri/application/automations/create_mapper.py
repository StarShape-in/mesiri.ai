"""Maps a confirmed workflow action into a CreateAutomationCommand.

Shape-mapping only -- no business validation here (that's
create_validation.py) and no name->user-id resolution (that's
name_resolution.py, run by the Handler since it needs a DB round trip).
Mirrors application/projects/create_site_mapper.py.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_commands import CreateAutomationCommand


def build_command(confirmed: ConfirmedActionV2) -> CreateAutomationCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    day_of_week = fields.get("day_of_week")
    return CreateAutomationCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        project_id=str(draft.project_id) if draft.project_id else None,
        site_id=str(draft.site_id) if draft.site_id else None,
        action=str(fields.get("action") or ""),
        audience=str(fields.get("audience") or "SELF"),
        audience_user_ids=[str(u) for u in fields["audience_user_ids"]]
        if fields.get("audience_user_ids")
        else None,
        audience_names=[str(n) for n in fields["audience_names"]]
        if fields.get("audience_names")
        else None,
        audience_role=fields.get("audience_role"),
        message=fields.get("message"),
        frequency=str(fields.get("frequency") or "DAILY"),
        day_of_week=int(day_of_week) if day_of_week is not None else None,
        time_of_day=str(fields.get("time_of_day") or ""),
        timezone=str(fields.get("timezone") or "UTC"),
        correlation_id=confirmed.correlation_id,
    )
