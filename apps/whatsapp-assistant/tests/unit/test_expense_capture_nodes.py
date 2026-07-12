"""Expense capture workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.expense_capture.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.EXPENSE_SUBMIT.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": SITE,
        "collected_fields": fields,
    }


def test_build_draft_expense():
    state = _base_state({"amount": 250, "category": "materials", "description": "cement bags"})
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_EXPENSE
    assert draft.fields == {"amount": 250, "category": "materials", "description": "cement bags"}
    assert draft.workflow_instance_id == "wf_1"
    assert draft.correlation_id == "cor_1"
    assert draft.organization_id == ORG
    assert draft.project_id == PRJ
    assert draft.site_id == SITE


def test_build_draft_missing_collected_fields_defaults_empty():
    state = _base_state({})
    del state["collected_fields"]
    update = build_draft(state)
    assert update["draft_action"].fields == {}


def test_request_confirmation_sets_prompt_from_draft():
    state = _base_state({"amount": 250, "category": "materials"})
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Expense" in prompt
    assert "250" in prompt
    assert "materials" in prompt
    assert "YES" in prompt
