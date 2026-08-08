"""Maps a confirmed workflow action into a CreateUserCommand.

Shape-mapping only — no business validation here (that's
create_user_validation.py, run separately by the Handler). Mirrors
application/projects/add_member_mapper.py.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_user_commands import CreateUserCommand


def build_command(confirmed: ConfirmedActionV2) -> CreateUserCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    return CreateUserCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        full_name=str(fields.get("full_name") or ""),
        whatsapp_number=str(fields.get("whatsapp_number") or ""),
        role=str(fields.get("role") or "SITE_ENGINEER"),
        correlation_id=confirmed.correlation_id,
    )
