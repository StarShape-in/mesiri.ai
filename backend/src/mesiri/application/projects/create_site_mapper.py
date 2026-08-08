"""Maps a confirmed workflow action into a CreateSiteCommand.

Shape-mapping only — no business validation here (that's
create_site_validation.py, run separately by the Handler). Mirrors
create_mapper.py, with one difference: `project_id` comes from the
DraftActionV2's own scope field (set by workflows/site_create/nodes.py from
the context-resolved project), never from `fields`.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_site_commands import CreateSiteCommand


def build_command(confirmed: ConfirmedActionV2) -> CreateSiteCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    return CreateSiteCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        project_id=str(draft.project_id or ""),
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        name=str(fields.get("name") or ""),
        location=fields.get("location"),
        correlation_id=confirmed.correlation_id,
    )
