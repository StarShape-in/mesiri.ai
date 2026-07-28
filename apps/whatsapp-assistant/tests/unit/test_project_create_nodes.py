"""Project create workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.project_create.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.PROJECT_CREATE.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


def test_build_draft_with_name():
    state = _base_state({"name": "Skyline Towers"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.CREATE_PROJECT
    assert draft.fields == {"name": "Skyline Towers"}


def test_build_draft_with_location_and_client():
    state = _base_state({"name": "Skyline Towers", "location": "Kochi", "client": "ABC Builders"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["location"] == "Kochi"
    assert draft.fields["client"] == "ABC Builders"


def test_request_confirmation_prompt_with_name_only():
    state = _base_state({"name": "Skyline Towers"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Create a new project" in prompt
    assert "Skyline Towers" in prompt
    assert "YES" in prompt
    assert "Location" not in prompt
    assert "Client" not in prompt


def test_request_confirmation_prompt_includes_location_and_client_when_present():
    state = _base_state({"name": "Skyline Towers", "location": "Kochi", "client": "ABC Builders"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Kochi" in prompt
    assert "ABC Builders" in prompt


def test_build_draft_missing_name_asks_instead_of_building_an_incomplete_draft():
    """The gap AI extraction can open: semantic_type resolved but name
    didn't. No draft at all -- workflows/project_create/graph.py routes
    this straight to END (see WorkflowDefinition.allows_completion_without_
    draft in workflows/registry.py), same as account_admin's own
    completeness check."""
    state = _base_state({})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "called" in update["pending_prompt"].lower()


def test_build_draft_blank_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"name": "   "})
    update = build_draft(state)
    assert "draft_action" not in update
