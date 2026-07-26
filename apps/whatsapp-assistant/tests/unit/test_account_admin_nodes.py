"""Account admin workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.account_admin.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.ACCOUNT_ADMIN.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


def test_build_draft_create():
    state = _base_state({"action": "create", "name": "Site Cash", "account_type": "cash"})
    draft = build_draft(state)["draft_action"]
    assert draft.action_type is DraftActionType.MANAGE_MONEY_ACCOUNT
    assert draft.fields == {"action": "create", "name": "Site Cash", "account_type": "cash"}


def test_request_confirmation_create_prompt():
    state = _base_state({"action": "create", "name": "Site Cash", "account_type": "cash"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Create a new account" in prompt
    assert "Site Cash" in prompt
    assert "YES" in prompt


def test_request_confirmation_rename_prompt():
    state = _base_state({"action": "rename", "target_name": "Site Cash", "new_name": "Kochi Cash"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Rename" in prompt
    assert "Site Cash" in prompt
    assert "Kochi Cash" in prompt


def test_request_confirmation_deactivate_prompt():
    state = _base_state({"action": "deactivate", "target_name": "Site Cash"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Deactivate account" in prompt
    assert "Site Cash" in prompt


def test_build_draft_create_missing_name_asks_instead_of_building_an_incomplete_draft():
    """The gap AI extraction opened, that the deterministic parser never
    could: `action` resolved but the action-specific field didn't. No draft
    at all -- workflows/account_admin/graph.py routes this straight to END
    (see WorkflowDefinition.allows_completion_without_draft in
    workflows/registry.py)."""
    state = _base_state({"action": "create"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "new account" in update["pending_prompt"].lower()


def test_build_draft_rename_missing_new_name_asks():
    state = _base_state({"action": "rename", "target_name": "Site Cash"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "renamed" in update["pending_prompt"].lower()


def test_build_draft_deactivate_missing_target_asks():
    state = _base_state({"action": "deactivate"})
    update = build_draft(state)
    assert "draft_action" not in update


def test_build_draft_unrecognized_action_asks_instead_of_crashing():
    state = _base_state({"action": "delete", "target_name": "Site Cash"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert update["pending_prompt"]


def test_build_draft_missing_action_entirely_asks_instead_of_crashing():
    state = _base_state({})
    update = build_draft(state)
    assert "draft_action" not in update
    assert update["pending_prompt"]
