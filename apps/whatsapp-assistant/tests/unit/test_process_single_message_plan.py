"""End-to-end regression anchor for Phase A4 of
docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md: an ORDINARY single-intent
message (~95% of real traffic) now becomes a size-1 Plan too, not a separate
path -- but must produce byte-identical reply text to before this phase,
both on the initial confirmation prompt and on the closing side once that
one step resolves.

The starting-side guarantee (no "(1 of 1) " prefix) falls out structurally
from runtime/plan_executor.py's _progress_prefix already returning "" for a
size-1 plan -- true regardless of this phase. The closing-side guarantee (no
extra "*Here's what I did:*" message after the step's own confirmation
reply) is the one Phase A4 actually had to build:
PlanOrigin.SINGLE_MESSAGE plus _start_next_runnable's suppression of it.
Neither guarantee had an end-to-end test before this file -- every existing
test either stops after the initial prompt (never simulates the follow-up
"Yes") or drives plan_executor.py directly with hand-built Plans that were
never SINGLE_MESSAGE-origin in the first place.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from context import seed
from context.identity_bridge import deterministic_canonical_uuid
from context.resolver import ContextResolver
from interactions.handler import InteractionHandler
from interactions.ports import ExecutionDispatcher
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai.fakes import FakeExtractionProvider, FakeVisionProvider, FakeVoiceExtractionProvider
from mesiri_ai.models import ExtractionResult
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from planner import Planner
from planning.plan import PlanOrigin, StepStatus
from planning.plan_store import PlanStore
from runtime.inbound_journey import process_inbound_message
from runtime.plan_executor import advance_plan
from understanding.pipeline import UnderstandingPipeline
from workflows import WorkflowRuntime
from workflows.fakes import FakeCompiledGraph, FakeWorkflowInstanceRepository, FakeWorkflowRegistry

_ORG_UUID = "11111111-1111-4111-8111-111111111111"
_USR_UUID = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


class _RecordingSender:
    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []

    async def send_text(self, wa_id: str, body: str) -> None:
        self.texts.append((wa_id, body))


class _SucceedingDispatcher(ExecutionDispatcher):
    async def dispatch(self, confirmed) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=confirmed.confirmed_action_id,
            material_row_id="66666666-6666-4666-8666-666666666666",
        )


class _Actor:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


def _message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.single.1",
        correlation_id="cor_single_1",
        sender=SenderInfo(wa_id=seed.WA_ENGINEER, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 31, 11, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="used 40 bags cement",
    )


def _extraction() -> FakeExtractionProvider:
    return FakeExtractionProvider(
        ExtractionResult(
            semantic_type="material_update",
            fields={
                "material_name": "cement",
                "quantity": 40,
                "unit": "bags",
                "direction": "used",
                # no work_item -- a genuinely single-segment report
            },
            provider="fake",
        )
    )


def _pipeline() -> UnderstandingPipeline:
    return UnderstandingPipeline(
        voice_extraction=FakeVoiceExtractionProvider(),
        vision=FakeVisionProvider(),
        extraction=_extraction(),
        object_storage=FakeObjectStorage(),
    )


def _draft(instance_id: str) -> DraftActionV2:
    return DraftActionV2(
        draft_id=f"d_{instance_id}",
        correlation_id="cor_single_1",
        workflow_instance_id=instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_USAGE,
        organization_id=_ORG_UUID,
        user_id=_USR_UUID,
        fields={"material_name": "cement", "quantity": 40, "unit": "bags"},
    )


async def test_ordinary_single_message_starts_with_no_plan_prefix_and_becomes_a_size_one_plan():
    plan_store = PlanStore(_FakeRedis())
    sender = _RecordingSender()
    graph = FakeCompiledGraph(
        {"draft_action": _draft("wf_single"), "pending_prompt": "Confirm 40 bags cement used?"}
    )
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_USAGE: graph}),
        repo=FakeWorkflowInstanceRepository(),
    )
    resolved_user_id = deterministic_canonical_uuid(seed.USER_ENGINEER)

    await process_inbound_message(
        _message(),
        actor_user_id=resolved_user_id,
        pipeline=_pipeline(),
        context_resolver=ContextResolver(seed.build_dependencies()),
        planner=Planner(),
        workflow_runtime=runtime,
        interaction_handler=InteractionHandler(workflow_runtime=runtime),
        send_text=sender.send_text,
        plan_store=plan_store,
    )

    # Byte-identical to before Phase A4: no "(1 of 1) " prefix -- the reply
    # starts with exactly the graph's own pending_prompt, nothing prepended
    # ("Reply Yes / No" is render_workflow_run_reply_spec's own existing
    # fallback hint, unrelated to and unchanged by this phase).
    assert len(sender.texts) == 1
    _wa_id, body = sender.texts[0]
    assert body.startswith("Confirm 40 bags cement used?")
    assert not body.startswith("(1 of 1)")

    plan = await plan_store.get_plan(user_id=resolved_user_id)
    assert plan is not None
    assert len(plan.steps) == 1
    assert plan.origin is PlanOrigin.SINGLE_MESSAGE
    s1 = plan.step("s1")
    assert s1 is not None
    assert s1.workflow_key is WorkflowKey.MATERIAL_USAGE
    assert s1.status is StepStatus.RUNNING
    assert s1.workflow_instance_id is not None


async def test_confirming_the_single_step_produces_no_extra_closing_message():
    """The whole point of Phase A4's origin-based suppression: advance_plan
    must return None here, not a "*Here's what I did:*" ReplySpec -- that
    would be a brand new, unrequested second message for ~95% of traffic."""
    plan_store = PlanStore(_FakeRedis())
    sender = _RecordingSender()
    graph = FakeCompiledGraph(
        {"draft_action": _draft("wf_single"), "pending_prompt": "Confirm 40 bags cement used?"}
    )
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_USAGE: graph}),
        repo=FakeWorkflowInstanceRepository(),
    )
    interaction_handler = InteractionHandler(
        workflow_runtime=runtime, dispatcher=_SucceedingDispatcher()
    )
    resolved_user_id = deterministic_canonical_uuid(seed.USER_ENGINEER)

    await process_inbound_message(
        _message(),
        actor_user_id=resolved_user_id,
        pipeline=_pipeline(),
        context_resolver=ContextResolver(seed.build_dependencies()),
        planner=Planner(),
        workflow_runtime=runtime,
        interaction_handler=interaction_handler,
        send_text=sender.send_text,
        plan_store=plan_store,
    )

    yes_message = NormalizedMessage(
        message_id="wamid.single.yes",
        correlation_id="cor_single_yes",
        sender=SenderInfo(wa_id=seed.WA_ENGINEER, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 31, 11, 1, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="Yes",
    )
    handled = await interaction_handler.handle_fast_path(resolved_user_id, yes_message)
    assert handled is not None
    assert handled.next_segment_reply is None

    plan_reply = await advance_plan(
        handled, plan_store=plan_store, workflow_runtime=runtime, actor=_Actor(resolved_user_id)
    )

    assert plan_reply is None
    assert await plan_store.get_plan(user_id=resolved_user_id) is None
