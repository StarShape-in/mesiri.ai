"""Site create workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.site_create.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict, project_id: str | None = PROJ) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.SITE_CREATE.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": project_id,
        "site_id": None,
        "collected_fields": fields,
    }


def test_build_draft_with_resolved_project_and_name():
    state = _base_state({"name": "Block A"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.CREATE_SITE
    assert draft.project_id == PROJ
    assert draft.fields == {"name": "Block A"}


def test_build_draft_with_location():
    state = _base_state({"name": "Block A", "location": "North Yard"})
    draft = build_draft(state)["draft_action"]
    assert draft.fields["location"] == "North Yard"


def test_request_confirmation_prompt_with_name_only():
    state = _base_state({"name": "Block A"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Create a new site" in prompt
    assert "Block A" in prompt
    assert "YES" in prompt
    assert "Location" not in prompt


def test_request_confirmation_prompt_includes_location_when_present():
    state = _base_state({"name": "Block A", "location": "North Yard"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "North Yard" in prompt


def test_build_draft_unresolved_project_asks_instead_of_building_an_incomplete_draft():
    """The sender belongs to more than one project and didn't name one --
    context/resolver.py's project resolution came up empty. No draft at all
    -- workflows/site_create/graph.py routes this straight to END."""
    state = _base_state({"name": "Block A"}, project_id=None)
    update = build_draft(state)
    assert "draft_action" not in update
    assert "which project" in update["pending_prompt"].lower()


def test_build_draft_missing_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "called" in update["pending_prompt"].lower()


def test_build_draft_blank_name_asks_instead_of_building_an_incomplete_draft():
    state = _base_state({"name": "   "})
    update = build_draft(state)
    assert "draft_action" not in update


def test_build_draft_missing_project_takes_priority_over_missing_name():
    """Both unresolved -- ask about the project first, since a name alone
    is useless without knowing where to put the site."""
    state = _base_state({}, project_id=None)
    update = build_draft(state)
    assert "which project" in update["pending_prompt"].lower()
