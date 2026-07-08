"""InteractionHandler — unit tests (fakes only, no LangGraph, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from interactions.handler import InteractionHandler
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows import WorkflowRegistry, WorkflowResumeStatus, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
WF = "11111111-1111-4111-8111-1111111111aa"


def _message(text: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_reply_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text=text,
    )


def _awaiting_state() -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id=WF,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return WorkflowStateV2(
        workflow_instance_id=WF,
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="c1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=draft,
        pending_prompt="Confirm?",
    )


def _handler(repo: FakeWorkflowInstanceRepository) -> InteractionHandler:
    return InteractionHandler(WorkflowRuntime(registry=WorkflowRegistry(), repo=repo))


async def test_no_active_workflow_returns_none():
    handler = _handler(FakeWorkflowInstanceRepository())
    assert await handler.handle(USR, _message("yes")) is None


async def test_confirm_reply_resumes_and_returns_reply():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    handled = await handler.handle(USR, _message("yes"))

    assert handled is not None
    assert handled.result.status is WorkflowResumeStatus.CONFIRMED
    assert "Recorded" in handled.reply_text
    assert repo._rows[WF][0].phase is WorkflowPhase.CONFIRMED


async def test_unrelated_reply_falls_through_to_normal_journey():
    """A user with a pending confirmation can still send an unrelated message —
    it must NOT be swallowed by the active workflow."""
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    handled = await handler.handle(USR, _message("50 bags steel arrived at site B"))

    assert handled is None  # → caller runs the normal pipeline
    assert repo._rows[WF][0].phase is WorkflowPhase.AWAITING_CONFIRMATION  # untouched


async def test_duplicate_confirm_is_idempotent():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    first = await handler.handle(USR, _message("yes"))
    assert first.result.status is WorkflowResumeStatus.CONFIRMED

    # The workflow is no longer awaiting → a second "yes" finds nothing to resume.
    second = await handler.handle(USR, _message("yes"))
    assert second is None
    assert repo._rows[WF][1] == 1  # exactly one transition applied
