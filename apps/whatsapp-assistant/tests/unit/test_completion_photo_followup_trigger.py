"""InteractionHandler._resume_and_render -- the #25 AI Follow-up trigger.

A confirmed ADD_PROGRESS_UPDATE with update_kind=COMPLETED must (a) append
the completion-photo question to the reply and (b) set the hint so the next
photo skips the purpose picker. Every other update_kind, and every other
action_type, must do neither.
"""

from __future__ import annotations

from datetime import UTC, datetime

from interactions.completion_photo_hint import CompletionPhotoHintStore
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
ACTIVITY = "33333333-3333-4333-8333-333333333333"
WF = "11111111-1111-4111-8111-1111111111aa"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key, value, *, ttl_seconds=None) -> None:
        self._store[key] = value

    async def get_json(self, key):
        return self._store.get(key)


class _SucceedingDispatcher(ExecutionDispatcher):
    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key="idem_1",
            material_row_id=ACTIVITY,
        )


def _message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="yes",
    )


def _awaiting_progress_update_state(*, update_kind: str) -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id=WF,
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={"activity_id": ACTIVITY, "update_kind": update_kind, "narrative": "done"},
    )
    return WorkflowStateV2(
        workflow_instance_id=WF,
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
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


def _handler(repo: FakeWorkflowInstanceRepository, hint_store: CompletionPhotoHintStore):
    registry = WorkflowRegistry()
    registry._compiled[WorkflowKey.ACTIVITY_CONTINUATION] = _NoopGraph()
    return InteractionHandler(
        WorkflowRuntime(registry=registry, repo=repo),
        dispatcher=_SucceedingDispatcher(),
        completion_photo_hint_store=hint_store,
    )


async def test_completed_progress_update_appends_the_followup_and_sets_the_hint():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_progress_update_state(update_kind="COMPLETED"), version=0)
    hint_store = CompletionPhotoHintStore(_FakeRedis())
    handler = _handler(repo, hint_store)

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "completion photo" in handled.reply_text.lower()
    # Fire-and-forget (asyncio.ensure_future) -- give the loop a tick.
    import asyncio

    await asyncio.sleep(0)
    assert await hint_store.pop_hint(user_id=USR) == ACTIVITY


async def test_progress_update_appends_neither_for_a_non_completed_kind():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_progress_update_state(update_kind="PROGRESS"), version=0)
    hint_store = CompletionPhotoHintStore(_FakeRedis())
    handler = _handler(repo, hint_store)

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "completion photo" not in handled.reply_text.lower()

    import asyncio

    await asyncio.sleep(0)
    assert await hint_store.pop_hint(user_id=USR) is None


async def test_no_hint_store_wired_is_a_safe_no_op():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_progress_update_state(update_kind="COMPLETED"), version=0)
    registry = WorkflowRegistry()
    registry._compiled[WorkflowKey.ACTIVITY_CONTINUATION] = _NoopGraph()
    handler = InteractionHandler(
        WorkflowRuntime(registry=registry, repo=repo),
        dispatcher=_SucceedingDispatcher(),
        # completion_photo_hint_store intentionally omitted
    )

    handled = await handler.handle_fast_path(USR, _message())

    assert handled is not None
    assert "completion photo" not in handled.reply_text.lower()
