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
