"""Add-project-member workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.add_project_member.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict, project_id: str | None = PROJ) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.ADD_PROJECT_MEMBER.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": project_id,
        "site_id": None,
        "collected_fields": fields,
    }


def test_build_draft_with_resolved_project_and_name_defaults_role():
    state = _base_state({"member_name": "Rajesh"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.ADD_PROJECT_MEMBER
    assert draft.project_id == PROJ
    assert draft.fields["member_name"] == "Rajesh"
    assert draft.fields["role"] == "SITE_ENGINEER"


def test_build_draft_normalizes_role_hint():
    state = _base_state({"member_name": "Priya", "role": "project manager"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["role"] == "PROJECT_MANAGER"


def test_build_draft_normalizes_unrecognized_role_hint_to_default():
    state = _base_state({"member_name": "Priya", "role": "supervisor"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["role"] == "SITE_ENGINEER"


def test_build_draft_carries_created_by_role():
    state = _base_state({"member_name": "Rajesh", "created_by_role": "ADMIN"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["created_by_role"] == "ADMIN"


def test_request_confirmation_prompt():
    state = _base_state({"member_name": "Rajesh"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Rajesh" in prompt
    assert "Site Engineer" in prompt
    assert "YES" in prompt


def test_build_draft_unresolved_project_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"member_name": "Rajesh"}, project_id=None)
    update = build_draft(state)
    assert "draft_action" not in update
    assert "which project" in update["pending_prompt"].lower()


def test_build_draft_missing_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "who" in update["pending_prompt"].lower()


def test_build_draft_blank_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"member_name": "   "})
    update = build_draft(state)
    assert "draft_action" not in update


def test_build_draft_missing_project_takes_priority_over_missing_name():
    state = _base_state({}, project_id=None)
    update = build_draft(state)
    assert "which project" in update["pending_prompt"].lower()
