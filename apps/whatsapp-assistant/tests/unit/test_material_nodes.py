"""Material workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.material.nodes import build_draft, request_confirmation


def _base_state(workflow_key: WorkflowKey, fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": workflow_key.value,
        "correlation_id": "cor_1",
        "organization_id": "org_1",
        "user_id": "usr_1",
        "project_id": "prj_1",
        "site_id": "site_1",
        "collected_fields": fields,
    }


def test_build_draft_material_receipt():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_MATERIAL_RECEIPT
    assert draft.fields == {"material_name": "cement", "quantity": 20, "unit": "bags"}
    assert draft.workflow_instance_id == "wf_1"
    assert draft.correlation_id == "cor_1"
    assert draft.organization_id == "org_1"
    assert draft.project_id == "prj_1"
    assert draft.site_id == "site_1"


def test_build_draft_material_usage():
    state = _base_state(
        WorkflowKey.MATERIAL_USAGE,
        {"material_name": "sand", "quantity": 5, "unit": "tons"},
    )
    update = build_draft(state)
    assert update["draft_action"].action_type is DraftActionType.RECORD_MATERIAL_USAGE


def test_build_draft_missing_collected_fields_defaults_empty():
    state = _base_state(WorkflowKey.MATERIAL_RECEIPT, {})
    del state["collected_fields"]
    update = build_draft(state)
    assert update["draft_action"].fields == {}


@pytest.mark.parametrize(
    "unsupported_key", [WorkflowKey.EXPENSE_SUBMIT, WorkflowKey.EQUIPMENT_USAGE]
)
def test_build_draft_unsupported_workflow_key_raises(unsupported_key: WorkflowKey) -> None:
    state = _base_state(unsupported_key, {})
    with pytest.raises(KeyError):
        build_draft(state)


def test_request_confirmation_sets_prompt_from_draft():
    state = _base_state(
        WorkflowKey.MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    state.update(build_draft(state))
    update = request_confirmation(state)
    prompt = update["pending_prompt"]
    assert "Material Receipt" in prompt
    assert "cement" in prompt
    assert "20" in prompt
    assert "YES" in prompt
