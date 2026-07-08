"""Contract tests for WorkflowState.v1.

WorkflowState is the durable, resumable snapshot serialized into
workflow_instances.state. It is the single source of truth for a running
workflow -- LangGraph itself runs without a checkpointer in M6.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.draft_action import DraftAction, DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.workflow_state import CONTRACT_VERSION, WorkflowState
from mesiri_contracts.context.enums import WorkflowPhase

REPO = pathlib.Path(__file__).resolve().parents[3]
FIXTURES = REPO / "scenarios" / "contracts" / "workflow_state"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


def test_workflow_state_round_trip_serialization_with_nested_draft_action():
    draft = DraftAction(
        draft_id="draft_test",
        correlation_id="cor_test",
        workflow_instance_id="wf_test",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id="org_001",
        user_id="usr_001",
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    state = WorkflowState(
        workflow_instance_id="wf_test",
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_test",
        organization_id="org_001",
        user_id="usr_001",
        project_id="prj_001",
        site_id="site_001",
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        collected_fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
        draft_action=draft,
        pending_prompt="Confirm: 20 bags cement received?",
    )
    dumped = state.model_dump(mode="json")
    assert dumped["version"] == "v1"
    assert dumped["phase"] == "awaiting_confirmation"
    assert dumped["workflow_key"] == "material.receipt"
    assert dumped["draft_action"]["action_type"] == "record_material_receipt"
    restored = WorkflowState.model_validate(dumped)
    assert restored == state


def test_workflow_state_minimal_fields():
    state = WorkflowState(
        workflow_instance_id="wf_min",
        workflow_key=WorkflowKey.MATERIAL_USAGE,
        correlation_id="cor_min",
        organization_id="org_001",
        user_id="usr_001",
    )
    assert state.phase is WorkflowPhase.ACTIVE
    assert state.collected_fields == {}
    assert state.draft_action is None
    assert state.pending_prompt is None
    assert state.project_id is None
    assert state.site_id is None


def test_workflow_state_extra_field_forbidden():
    with pytest.raises(ValidationError):
        WorkflowState.model_validate(
            {
                "workflow_instance_id": "wf_test",
                "workflow_key": "material.receipt",
                "correlation_id": "cor_test",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "confidence_level": "high",
            }
        )


def test_invalid_phase_enum_rejected():
    with pytest.raises(ValidationError):
        WorkflowState.model_validate(
            {
                "workflow_instance_id": "wf_test",
                "workflow_key": "material.receipt",
                "correlation_id": "cor_test",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "phase": "extremely_confused",
            }
        )


def test_invalid_workflow_key_enum_rejected():
    with pytest.raises(ValidationError):
        WorkflowState.model_validate(
            {
                "workflow_instance_id": "wf_test",
                "workflow_key": "not.a.real.key",
                "correlation_id": "cor_test",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


def test_required_organization_id():
    with pytest.raises(ValidationError):
        WorkflowState.model_validate(
            {
                "workflow_instance_id": "wf_test",
                "workflow_key": "material.receipt",
                "correlation_id": "cor_test",
                "user_id": "usr_001",
            }
        )


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    state = WorkflowState.model_validate(_load(path))
    assert state.version == CONTRACT_VERSION
    assert state.workflow_instance_id
    assert state.correlation_id
    assert isinstance(state.workflow_key, WorkflowKey)
    assert isinstance(state.phase, WorkflowPhase)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        WorkflowState.model_validate(_load(path))
