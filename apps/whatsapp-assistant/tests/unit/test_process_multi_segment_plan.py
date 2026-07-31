"""End-to-end regression anchor for Phase A2 of
docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md: the ONE case that produces
more than one CanonicalEvent from a single message today (a material report
naming its own work_item -- canonicalization/builder.py's
_build_linked_activity_segment) must become a Plan through
process_inbound_message, not a workflows/batch.py PendingBatchStore entry.

This exercises the real chain end-to-end (real ContextResolver against
context/seed's fixtures, real Planner, real WorkflowRuntime against fake
compiled graphs, real build_plan_from_segments) -- the level no prior test
covered. test_multi_segment_canonicalization.py only tests
build_canonical_events in isolation; test_batch_workflow.py only tests
workflows/batch.py's own functions in isolation. Neither ever drove this
through process_inbound_message, so the "regression anchor" the design doc
named did not exist as an automated test before this file.
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
from planning.plan import StepStatus
from planning.plan_store import PlanStore
from runtime.inbound_journey import process_inbound_message
from understanding.pipeline import UnderstandingPipeline
from workflows import WorkflowRuntime
from workflows.fakes import FakeCompiledGraph, FakeWorkflowInstanceRepository, FakeWorkflowRegistry


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
    """M8's real dispatcher isn't wired in this environment (no DB) -- a
    confirmed step must still produce a real ExecutionResult for
    plan_executor.advance_plan to mark it DONE and continue, exactly as
    test_completion_photo_followup_trigger.py's own fake does for the same
    reason."""

    async def dispatch(self, confirmed) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=confirmed.confirmed_action_id,
            material_row_id="55555555-5555-4555-8555-555555555555",
        )


class _Actor:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


def _message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.multi_segment.1",
        correlation_id="cor_multi_segment_1",
        sender=SenderInfo(wa_id=seed.WA_ENGINEER, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 31, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="used 40 bags cement for slab work",
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
                "work_item": "slab work",
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


_ORG_UUID = "11111111-1111-4111-8111-111111111111"
_USR_UUID = "22222222-2222-4222-8222-222222222222"


def _draft(instance_id: str) -> DraftActionV2:
    return DraftActionV2(
        draft_id=f"d_{instance_id}",
        correlation_id="cor_multi_segment_1",
        workflow_instance_id=instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_USAGE,
        organization_id=_ORG_UUID,
        user_id=_USR_UUID,
        fields={"material_name": "cement", "quantity": 40, "unit": "bags"},
    )


def _workflow_runtime() -> WorkflowRuntime:
    # Only the PRIMARY segment's graph (MATERIAL_USAGE) is ever invoked by
    # process_inbound_message itself -- the second segment (SITE_UPDATE, the
    # linked activity) only starts later, when plan_executor.advance_plan
    # confirms step s1 -- so it needs no graph registered here at all.
    graph = FakeCompiledGraph({"draft_action": _draft("wf_primary"), "pending_prompt": "Confirm 40 bags cement used?"})
    return WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_USAGE: graph}),
        repo=FakeWorkflowInstanceRepository(),
    )


async def test_material_usage_with_work_item_becomes_a_two_step_plan_not_a_batch_queue():
    plan_store = PlanStore(_FakeRedis())
    sender = _RecordingSender()

    resolved_user_id = deterministic_canonical_uuid(seed.USER_ENGINEER)
    await process_inbound_message(
        _message(),
        actor_user_id=resolved_user_id,
        pipeline=_pipeline(),
        context_resolver=ContextResolver(seed.build_dependencies()),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(workflow_runtime=_workflow_runtime()),
        send_text=sender.send_text,
        plan_store=plan_store,
    )

    # The primary segment's own confirmation prompt, prefixed with its
    # position in the plan -- same wording workflows/batch.py's
    # format_batch_prefix produced for the identical scenario.
    assert len(sender.texts) == 1
    _wa_id, body = sender.texts[0]
    assert body.startswith("(1 of 2) ")
    assert "Confirm 40 bags cement used?" in body

    plan = await plan_store.get_plan(user_id=resolved_user_id)
    assert plan is not None
    assert len(plan.steps) == 2

    s1 = plan.step("s1")
    assert s1 is not None
    assert s1.workflow_key is WorkflowKey.MATERIAL_USAGE
    assert s1.status is StepStatus.RUNNING
    assert s1.workflow_instance_id is not None

    s2 = plan.step("s2")
    assert s2 is not None
    assert s2.workflow_key is WorkflowKey.SITE_UPDATE
    assert s2.status is StepStatus.PENDING
    assert s2.fields.get("narrative") == "slab work"


async def test_confirming_the_primary_segment_advances_to_the_linked_activity():
    """Phase A3: the second segment must now be advanced by
    runtime/plan_executor.py's advance_plan (already called unconditionally
    after every resolved confirmation in message_journey.py), not by
    interactions/handler.py's own workflows/batch.py-based branch -- which
    this proves is truly inert (handled.next_segment_reply stays None) by
    driving the exact same interaction_handler.handle_fast_path call
    message_journey.py makes, not a hand-built substitute."""
    plan_store = PlanStore(_FakeRedis())
    sender = _RecordingSender()

    # ONE shared runtime (and its repo) across both calls below -- the
    # confirmation tap must resolve the SAME WorkflowInstance the initial
    # message started, exactly as message_journey.py's two calls share one
    # `workflow_runtime` for the whole request.
    site_update_graph = FakeCompiledGraph(
        {
            "draft_action": _draft("wf_site_update"),
            "pending_prompt": "Log this activity: slab work?",
        }
    )
    material_usage_graph = FakeCompiledGraph(
        {"draft_action": _draft("wf_primary"), "pending_prompt": "Confirm 40 bags cement used?"}
    )
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry(
            {
                WorkflowKey.MATERIAL_USAGE: material_usage_graph,
                WorkflowKey.SITE_UPDATE: site_update_graph,
            }
        ),
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
        message_id="wamid.multi_segment.yes",
        correlation_id="cor_multi_segment_yes",
        sender=SenderInfo(wa_id=seed.WA_ENGINEER, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 31, 10, 1, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="Yes",
    )
    handled = await interaction_handler.handle_fast_path(resolved_user_id, yes_message)
    assert handled is not None
    # The claim this whole phase rests on: nothing left in this handler
    # advances a multi-segment message -- see InteractionHandled.
    # next_segment_reply's docstring.
    assert handled.next_segment_reply is None

    from runtime.plan_executor import advance_plan

    plan_reply = await advance_plan(
        handled, plan_store=plan_store, workflow_runtime=runtime, actor=_Actor(resolved_user_id)
    )

    assert plan_reply is not None
    assert plan_reply.text.startswith("(2 of 2) ")
    assert "Log this activity: slab work?" in plan_reply.text

    plan = await plan_store.get_plan(user_id=resolved_user_id)
    assert plan is not None
    assert plan.step("s1").status is StepStatus.DONE
    assert plan.step("s2").status is StepStatus.RUNNING
    assert plan.step("s2").workflow_instance_id is not None
