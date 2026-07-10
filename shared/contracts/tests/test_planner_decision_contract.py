"""Contract tests for PlannerDecision.v1.

PlannerDecision is the routing decision between CanonicalEvent and the future
Workflow Registry (M6). Per the architecture's layer-ownership table the
Planner "returns a workflow_key" and must never own knowledge of a specific
graph. The model_validator here enforces the invariant that ``workflow_key``
is set if and only if ``decision_type`` is START_WORKFLOW — both invalid
combinations are covered below and via fixtures.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import (
    CONTRACT_VERSION,
    PlannerDecision,
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
FIXTURES = REPO / "scenarios" / "contracts" / "planner_decision"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Version constant
# ---------------------------------------------------------------------------


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


# ---------------------------------------------------------------------------
# PlannerDecision.v1
# ---------------------------------------------------------------------------


def test_planner_decision_round_trip_serialization():
    decision = PlannerDecision(
        correlation_id="cor_test",
        source_message_id="msg_test",
        causation_event_id="evt_test",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        reason=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        priority=PlannerPriority.HIGH,
        organization_id="org_001",
        user_id="usr_001",
        project_id="prj_001",
        site_id="site_001",
    )
    dumped = decision.model_dump(mode="json")
    assert dumped["version"] == "v1"
    assert dumped["decision_type"] == "start_workflow"
    assert dumped["workflow_key"] == "material.receipt"
    assert dumped["reason"] == "MaterialReceiptRequested"
    restored = PlannerDecision.model_validate(dumped)
    assert restored == decision


def test_planner_decision_minimal_fields():
    """Only the required fields (correlation_id, source_message_id, decision_type,
    reason, organization_id, user_id)."""
    decision = PlannerDecision(
        correlation_id="cor_min",
        source_message_id="msg_min",
        decision_type=PlannerDecisionType.DIRECT_REPLY,
        reason=CanonicalEventType.GENERAL_QUESTION_ASKED,
        organization_id="org_001",
        user_id="usr_001",
    )
    assert decision.workflow_key is None
    assert decision.priority is PlannerPriority.NORMAL
    assert decision.missing_fields == []
    assert decision.metadata == {}


def test_planner_decision_extra_field_forbidden():
    """PlannerDecision must never carry AI confidence scores (layer-ownership rule)."""
    with pytest.raises(ValidationError):
        PlannerDecision.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "decision_type": "direct_reply",
                "reason": "GeneralQuestionAsked",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "confidence_level": "high",
            }
        )


def test_invalid_decision_type_enum_rejected():
    with pytest.raises(ValidationError):
        PlannerDecision.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "decision_type": "maybe_workflow",
                "reason": "GeneralQuestionAsked",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


def test_required_organization_id():
    with pytest.raises(ValidationError):
        PlannerDecision.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "decision_type": "direct_reply",
                "reason": "GeneralQuestionAsked",
                "user_id": "usr_001",
            }
        )


# ---------------------------------------------------------------------------
# decision_type <-> workflow_key invariant
# ---------------------------------------------------------------------------


def test_start_workflow_requires_workflow_key():
    with pytest.raises(ValidationError):
        PlannerDecision(
            correlation_id="cor_test",
            source_message_id="msg_test",
            decision_type=PlannerDecisionType.START_WORKFLOW,
            workflow_key=None,
            reason=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
            organization_id="org_001",
            user_id="usr_001",
        )


@pytest.mark.parametrize(
    "decision_type",
    [PlannerDecisionType.CLARIFY, PlannerDecisionType.DIRECT_REPLY, PlannerDecisionType.IGNORE],
)
def test_non_start_workflow_forbids_workflow_key(decision_type: PlannerDecisionType) -> None:
    with pytest.raises(ValidationError):
        PlannerDecision(
            correlation_id="cor_test",
            source_message_id="msg_test",
            decision_type=decision_type,
            workflow_key=WorkflowKey.MATERIAL_RECEIPT,
            reason=CanonicalEventType.GENERAL_QUESTION_ASKED,
            organization_id="org_001",
            user_id="usr_001",
        )


# ---------------------------------------------------------------------------
# Fixture-driven contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    decision = PlannerDecision.model_validate(_load(path))
    assert decision.version == CONTRACT_VERSION
    assert decision.correlation_id
    assert decision.source_message_id
    assert decision.organization_id
    assert decision.user_id
    assert isinstance(decision.decision_type, PlannerDecisionType)
    assert isinstance(decision.reason, CanonicalEventType)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        PlannerDecision.model_validate(_load(path))
