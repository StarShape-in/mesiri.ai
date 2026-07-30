"""Unit tests for runtime/inbound_journey/plan_confirmation.py -- the
whole-plan preview's Yes/No tap (docs/execution/
COMPOSITE_REQUEST_PLAN_LAYER.md §8, P3)."""

from __future__ import annotations

from typing import Any

from channel.replies import PLAN_CONFIRM_NO_ROW_ID, PLAN_CONFIRM_YES_ROW_ID
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from planning.plan import Plan, PlanOrigin, PlanStep, StepStatus
from planning.plan_store import PlanStore
from runtime.inbound_journey.plan_confirmation import resume_pending_plan_confirmation
from workflows.runtime import WorkflowRunResult, WorkflowRunStatus

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


class _FakeWorkflowRuntime:
    def __init__(self, results: list[WorkflowRunResult]) -> None:
        self._results = list(results)
        self.start_calls: list[tuple[Any, Any]] = []

    async def start(self, decision, event):
        self.start_calls.append((decision, event))
        return self._results.pop(0)

    async def abandon_optional_question(self, user_id: str) -> None:
        return None


def _tap(row_id: str, *, modality: InputModality = InputModality.INTERACTIVE) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="msg_tap",
        correlation_id="cor_tap",
        sender={"wa_id": "15550001111"},
        timestamp="2026-07-30T10:00:00Z",
        modality=modality,
        metadata={"interactive_reply_id": row_id} if row_id else {},
    )


def _pending_plan(*, n_steps: int = 2) -> Plan:
    steps = [
        PlanStep(
            step_id="s1",
            workflow_key=WorkflowKey.PROJECT_CREATE,
            event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
            fields={"name": "Starship"},
        ),
    ]
    if n_steps > 1:
        steps.append(
            PlanStep(
                step_id="s2",
                workflow_key=WorkflowKey.CREATE_USER,
                event_type=CanonicalEventType.CREATE_USER_REQUESTED,
                fields={"full_name": "Hysam"},
            )
        )
    return Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=PlanOrigin.DECOMPOSITION,
        steps=tuple(steps),
    )


def _started(workflow_key, prompt: str, instance: str) -> WorkflowRunResult:
    draft = DraftActionV2(
        draft_id=f"d_{instance}",
        correlation_id=f"c_{instance}",
        workflow_instance_id=instance,
        action_type=DraftActionType.CREATE_PROJECT,
        organization_id=ORG,
        user_id=USR,
        project_id=None,
        site_id=None,
        fields={},
    )
    return WorkflowRunResult(
        status=WorkflowRunStatus.STARTED,
        workflow_key=workflow_key,
        correlation_id=f"c_{instance}",
        workflow_instance_id=instance,
        draft_action=draft,
        pending_prompt=prompt,
    )


async def test_returns_none_for_a_non_interactive_message():
    reply = await resume_pending_plan_confirmation(
        _tap("", modality=InputModality.TEXT),
        USR,
        plan_store=PlanStore(_FakeRedis()),
        workflow_runtime=_FakeWorkflowRuntime([]),
    )
    assert reply is None


async def test_returns_none_for_an_unrelated_row_id():
    """Any other tap (a project picker, a material picker, ...) must fall
    straight through -- this is dispatched alongside those, not instead of."""
    reply = await resume_pending_plan_confirmation(
        _tap("proj_some-other-id"),
        USR,
        plan_store=PlanStore(_FakeRedis()),
        workflow_runtime=_FakeWorkflowRuntime([]),
    )
    assert reply is None


async def test_no_discards_the_plan():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_pending_plan())
    assert await store.get_plan(user_id=USR) is not None

    reply = await resume_pending_plan_confirmation(
        _tap(PLAN_CONFIRM_NO_ROW_ID),
        USR,
        plan_store=store,
        workflow_runtime=_FakeWorkflowRuntime([]),
    )

    assert reply is not None
    assert "won't do" in reply.text.lower()
    assert await store.get_plan(user_id=USR) is None


async def test_no_on_an_already_expired_plan_is_a_harmless_no_op():
    store = PlanStore(_FakeRedis())
    reply = await resume_pending_plan_confirmation(
        _tap(PLAN_CONFIRM_NO_ROW_ID),
        USR,
        plan_store=store,
        workflow_runtime=_FakeWorkflowRuntime([]),
    )
    assert reply is not None
    assert "won't do" in reply.text.lower()


async def test_yes_with_no_plan_waiting_says_it_expired():
    reply = await resume_pending_plan_confirmation(
        _tap(PLAN_CONFIRM_YES_ROW_ID),
        USR,
        plan_store=PlanStore(_FakeRedis()),
        workflow_runtime=_FakeWorkflowRuntime([]),
    )
    assert reply is not None
    assert "expired" in reply.text.lower()


async def test_yes_begins_the_first_step_and_leaves_the_rest_pending():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_pending_plan())
    runtime = _FakeWorkflowRuntime(
        [_started(WorkflowKey.PROJECT_CREATE, "Create project Starship?", "wf_1")]
    )

    reply = await resume_pending_plan_confirmation(
        _tap(PLAN_CONFIRM_YES_ROW_ID),
        USR,
        plan_store=store,
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert "Create project Starship?" in reply.text
    assert len(runtime.start_calls) == 1

    plan = await store.get_plan(user_id=USR)
    assert plan.step("s1").status is StepStatus.RUNNING
    assert plan.step("s1").workflow_instance_id == "wf_1"
    assert plan.step("s2").status is StepStatus.PENDING


async def test_yes_is_safe_to_retry_after_a_start_failure():
    """A tap that fails mid-begin must leave the plan usable for a retry --
    not clear it out from under the user."""
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_pending_plan(n_steps=1))
    runtime = _FakeWorkflowRuntime([RuntimeError("boom")])

    reply = await resume_pending_plan_confirmation(
        _tap(PLAN_CONFIRM_YES_ROW_ID),
        USR,
        plan_store=store,
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert "couldn't start" in reply.text.lower()
    # The plan is untouched -- still there, first step still PENDING.
    plan = await store.get_plan(user_id=USR)
    assert plan is not None
    assert plan.step("s1").status is StepStatus.PENDING
