"""Maps a confirmed workflow action into an AddProjectMemberCommand.

Shape-mapping only — no business validation and no name resolution here
(validation is add_member_validation.py; resolution is name_resolution.py,
run by the Handler). Mirrors create_site_mapper.py, with `project_id`
coming from the DraftActionV2's own scope field (set by
workflows/add_project_member/nodes.py from the context-resolved project),
never from `fields`.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .add_member_commands import AddProjectMemberCommand


def build_command(confirmed: ConfirmedActionV2) -> AddProjectMemberCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    return AddProjectMemberCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        project_id=str(draft.project_id or ""),
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        member_name=str(fields.get("member_name") or ""),
        role=str(fields.get("role") or "SITE_ENGINEER"),
        correlation_id=confirmed.correlation_id,
    )
