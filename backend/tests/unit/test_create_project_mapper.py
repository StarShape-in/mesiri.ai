"""ConfirmedActionV2 -> CreateProjectCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from mesiri.application.projects.create_mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_PROJECT,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_name_only():
    cmd = build_command(_confirmed({"name": "Skyline Towers"}))
    assert cmd.idempotency_key == "wf_1"
    assert cmd.name == "Skyline Towers"
    assert cmd.location is None
    assert cmd.client is None
    assert cmd.created_by == USR


def test_maps_optional_location_and_client():
    cmd = build_command(
        _confirmed({"name": "Skyline Towers", "location": "Kochi", "client": "ABC Builders"})
    )
    assert cmd.location == "Kochi"
    assert cmd.client == "ABC Builders"


def test_maps_created_by_role():
    """Seeded by runtime/inbound_journey.py's _seed_project_create_role,
    validated in application/projects/create_validation.py -- defense-in-
    depth for the role gate that already blocks a disallowed role earlier."""
    cmd = build_command(_confirmed({"name": "Skyline Towers", "created_by_role": "PROJECT_MANAGER"}))
    assert cmd.created_by_role == "PROJECT_MANAGER"


def test_missing_created_by_role_defaults_to_none():
    cmd = build_command(_confirmed({"name": "Skyline Towers"}))
    assert cmd.created_by_role is None


def test_missing_name_defaults_to_empty_string():
    """build_draft in workflows/project_create/nodes.py never lets an empty
    name reach confirmation, but the mapper itself must not raise on a
    malformed draft -- validate() in the Handler is what rejects it."""
    cmd = build_command(_confirmed({}))
    assert cmd.name == ""
