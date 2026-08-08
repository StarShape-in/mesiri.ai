"""Maps a confirmed workflow action into a CreateProjectCommand.

Shape-mapping only — no business validation here (that's create_validation.py,
run separately by the Handler). Mirrors application/finance/mapper.py.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_commands import CreateProjectCommand


def build_command(confirmed: ConfirmedActionV2) -> CreateProjectCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    return CreateProjectCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        name=str(fields.get("name") or ""),
        location=fields.get("location"),
        client=fields.get("client"),
        description=fields.get("description"),
        correlation_id=confirmed.correlation_id,
    )
