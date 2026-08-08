"""WorkflowRuntime.start single-active guard — unit tests (fakes only)."""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows import WorkflowRunStatus, WorkflowRuntime
from workflows.fakes import FakeCompiledGraph, FakeWorkflowInstanceRepository, FakeWorkflowRegistry

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _decision() -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_2",
        source_message_id="msg_2",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        reason=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
    )


def _event() -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_2",
        correlation_id="cor_2",
        source_message_id="msg_2",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "sand", "quantity": 5, "unit": "tons"},
    )


def _pending_state() -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d0",
        correlation_id="cor_1",
        workflow_instance_id="11111111-1111-4111-8111-1111111111aa",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return WorkflowStateV2(
        workflow_instance_id="11111111-1111-4111-8111-1111111111aa",
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=draft,
        pending_prompt="Confirm: 20 bags cement received?",
    )


async def test_start_blocked_when_user_already_has_awaiting_confirmation():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_pending_state(), version=0)
    graph = FakeCompiledGraph({"draft_action": None, "pending_prompt": "x"})
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_RECEIPT: graph}), repo=repo
    )

    result = await runtime.start(_decision(), _event())

    assert result.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION
    assert result.pending_prompt == "Confirm: 20 bags cement received?"
    # nothing new saved — still just the one pending instance
    assert len(repo.saved) == 1


async def test_start_proceeds_when_no_awaiting_confirmation():
    repo = FakeWorkflowInstanceRepository()
    draft = DraftActionV2(
        draft_id="dn",
        correlation_id="cor_2",
        workflow_instance_id="placeholder",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "sand", "quantity": 5, "unit": "tons"},
    )
    graph = FakeCompiledGraph({"draft_action": draft, "pending_prompt": "Confirm sand?"})
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_RECEIPT: graph}), repo=repo
    )

    result = await runtime.start(_decision(), _event())

    assert result.status is WorkflowRunStatus.STARTED
    assert len(repo.saved) == 1
    assert repo.saved[0].phase is WorkflowPhase.AWAITING_CONFIRMATION
