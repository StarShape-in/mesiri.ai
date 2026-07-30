"""InteractionHandler._resume_and_render -- the post-create readiness nudge.

A confirmed CREATE_PROJECT execution must append the "still needs a site /
team members" follow-up to the reply. Every other action_type, and a failed
CREATE_PROJECT execution, must not.
"""

from __future__ import annotations

from datetime import UTC, datetime

from interactions.handler import InteractionHandler
from interactions.ports import ExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows import WorkflowRegistry, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
WF = "11111111-1111-4111-8111-1111111111aa"


class _SucceedingDispatcher(ExecutionDispatcher):
    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key="idem_1",
            material_row_id=PROJECT,
        )


class _RejectingDispatcher(ExecutionDispatcher):
    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key="idem_1",
            rejection_reasons=["duplicate name"],
        )


def _message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Admin"),
        timestamp=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="yes",
    )


def _awaiting_state(action_type: DraftActionType) -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id=WF,
        action_type=action_type,
        organization_id=ORG,
        user_id=USR,
        fields={"name": "Skyline Towers"},
    )
    return WorkflowStateV2(
        workflow_instance_id=WF,
        workflow_key=WorkflowKey.PROJECT_CREATE,
        correlation_id="c1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=draft,
        pending_prompt="Confirm?",
    )


class _NoopGraph:
    async def ainvoke(self, state: dict) -> dict:
        return {}


def _handler(repo: FakeWorkflowInstanceRepository, dispatcher: ExecutionDispatcher):
    registry = WorkflowRegistry()
    registry._compiled[WorkflowKey.PROJECT_CREATE] = _NoopGraph()
    return InteractionHandler(
        WorkflowRuntime(registry=registry, repo=repo),
        dispatcher=dispatcher,
    )


async def test_created_project_appends_the_readiness_followup():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(DraftActionType.CREATE_PROJECT), version=0)
    handler = _handler(repo, _SucceedingDispatcher())

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "still needs" in handled.reply_text.lower()
    assert "site" in handled.reply_text.lower()


async def test_rejected_project_create_does_not_append_the_followup():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(DraftActionType.CREATE_PROJECT), version=0)
    handler = _handler(repo, _RejectingDispatcher())

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "still needs" not in handled.reply_text.lower()


async def test_other_action_types_do_not_append_the_followup():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(DraftActionType.CREATE_SITE), version=0)
    handler = _handler(repo, _SucceedingDispatcher())

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "still needs" not in handled.reply_text.lower()
