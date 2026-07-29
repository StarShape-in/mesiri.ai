"""ConfirmedActionV2 -> CreateSiteCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from mesiri.application.projects.create_site_mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed(fields: dict, project_id: str | None = PROJ) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_SITE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_project_id_from_draft_scope_not_fields():
    """project_id comes from DraftActionV2's own scope field (set by
    workflows/site_create/nodes.py from context resolution), never from
    fields -- see the module docstring."""
    cmd = build_command(_confirmed({"name": "Block A"}, project_id=PROJ))
    assert cmd.project_id == PROJ


def test_maps_name_only():
    cmd = build_command(_confirmed({"name": "Block A"}))
    assert cmd.idempotency_key == "wf_1"
    assert cmd.name == "Block A"
    assert cmd.location is None
    assert cmd.created_by == USR


def test_maps_optional_location():
    cmd = build_command(_confirmed({"name": "Block A", "location": "North Yard"}))
    assert cmd.location == "North Yard"


def test_maps_created_by_role():
    cmd = build_command(_confirmed({"name": "Block A", "created_by_role": "PROJECT_MANAGER"}))
    assert cmd.created_by_role == "PROJECT_MANAGER"


def test_missing_created_by_role_defaults_to_none():
    cmd = build_command(_confirmed({"name": "Block A"}))
    assert cmd.created_by_role is None


def test_missing_project_id_defaults_to_empty_string():
    """build_draft in workflows/site_create/nodes.py never lets an
    unresolved project reach confirmation, but the mapper itself must not
    raise on a malformed draft -- validate() in the Handler is what rejects
    it."""
    cmd = build_command(_confirmed({"name": "Block A"}, project_id=None))
    assert cmd.project_id == ""


def test_missing_name_defaults_to_empty_string():
    cmd = build_command(_confirmed({}))
    assert cmd.name == ""
