"""Unit tests for the CREATE_USER -> ADD_PROJECT_MEMBER chain
(ENTITY_RESOLUTION_PLAN.md sections 3.3/8.1): start_member_create_plan and
advance_member_plan_after_user_created.

The live bug this completes: a Malayalam message named a real user who did
not yet have a Mesiri account. Missing's "Yes, create" tap must not just
create the user and stop -- it has to finish the original "add them to the
project" request the user actually sent. Fakes only: no live DB, no
LangGraph, no HTTP.
"""

from __future__ import annotations

from typing import Any

from interactions.handler import InteractionHandled
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from planning.plan import StepStatus
from planning.plan_store import PlanStore
from runtime.inbound_journey.resume import (
    advance_member_plan_after_user_created,
    start_member_create_plan,
)
from workflows.runtime import (
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
    WorkflowRunStatus,
)

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


def _plan_store() -> PlanStore:
    return PlanStore(_FakeRedis())


class _Actor:
    def __init__(self, *, user_id: str = USR, organization_id: str = ORG, role: str = "ADMIN"):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role


#: The one CREATE_USER WorkflowInstance these fixtures model. The started
#: workflow and the confirmation that later resolves it are the SAME
#: instance in reality, so both _awaiting_input and
#: _handled_create_user_success use this id -- advance_member_plan_after_
#: user_created matches on it to tell "the CREATE_USER my plan is waiting
#: on" apart from any other CREATE_USER the same user starts inside the
#: plan's TTL.
CREATE_USER_WF = "wf_1"


def _awaiting_input(
    workflow_key, pending_prompt: str, *, workflow_instance_id: str = CREATE_USER_WF
) -> WorkflowRunResult:
    return WorkflowRunResult(
        status=WorkflowRunStatus.AWAITING_INPUT,
        workflow_key=workflow_key,
        correlation_id="c1",
        workflow_instance_id=workflow_instance_id,
        pending_prompt=pending_prompt,
    )


def _started(workflow_key, pending_prompt: str) -> WorkflowRunResult:
    draft = DraftActionV2(
        draft_id="d_new",
        correlation_id="c2",
        workflow_instance_id="wf_new2",
        action_type=DraftActionType.ADD_PROJECT_MEMBER,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=None,
        fields={},
    )
    return WorkflowRunResult(
        status=WorkflowRunStatus.STARTED,
        workflow_key=workflow_key,
        correlation_id="c2",
        workflow_instance_id="wf_new2",
        draft_action=draft,
        pending_prompt=pending_prompt,
    )


class _FakeWorkflowRuntime:
    """Records every start() call and replays canned results in order."""

    def __init__(self, results: list[WorkflowRunResult]) -> None:
        self._results = list(results)
        self.start_calls: list[tuple[Any, Any]] = []

    async def start(self, decision, event):
        self.start_calls.append((decision, event))
        return self._results.pop(0)

    async def abandon_optional_question(self, user_id: str) -> None:
        return None


def _original_event(member_name: str = "Hysam", role: str = "PROJECT_MANAGER") -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_original",
        source_message_id="msg_1",
        event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields={"member_name": member_name, "role": role, "created_by_role": "PROJECT_MANAGER"},
    )


async def test_start_member_create_plan_persists_the_two_step_plan_and_starts_create_user():
    store = _plan_store()
    runtime = _FakeWorkflowRuntime(
        [
            _awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")
        ]
    )
    prompt = await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=runtime,
    )
    assert prompt == "What's their WhatsApp number?"

    # A real CREATE_USER workflow was started, seeded with the name hint.
    assert len(runtime.start_calls) == 1
    decision, event = runtime.start_calls[0]
    assert decision.decision_type is PlannerDecisionType.START_WORKFLOW
    assert decision.workflow_key is WorkflowKey.CREATE_USER
    assert event.fields["full_name"] == "Hysam"
    assert event.fields["role"] == "PROJECT_MANAGER"

    # The plan is durable: two steps, create_user RUNNING, add_member PENDING
    # with member_name as a StepRef -- not resolved yet.
    plan = await store.get_plan(user_id=USR)
    assert plan is not None
    assert [s.step_id for s in plan.steps] == ["create_user", "add_member"]
    create_step = plan.step("create_user")
    add_step = plan.step("add_member")
    assert create_step.status.value == "running"
    assert add_step.status.value == "pending"
    assert add_step.depends_on == frozenset({"create_user"})


async def test_start_member_create_plan_clears_the_plan_if_the_start_fails():
    store = _plan_store()
    runtime = _FakeWorkflowRuntime(
        [
            WorkflowRunResult(
                status=WorkflowRunStatus.FAILED,
                workflow_key=WorkflowKey.CREATE_USER,
                correlation_id="c1",
            )
        ]
    )
    prompt = await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=runtime,
    )
    assert prompt is None
    assert await store.get_plan(user_id=USR) is None


def _confirmed_create_user(full_name: str = "Hysam") -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_cu",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_USER,
        organization_id=ORG,
        user_id=USR,
        project_id=None,
        site_id=None,
        fields={"full_name": full_name, "whatsapp_number": "919876543210", "role": "PROJECT_MANAGER"},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_cu",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def _handled_create_user_success(full_name: str = "Hysam") -> InteractionHandled:
    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf_1",
        correlation_id="cor_cu",
        confirmed_action=_confirmed_create_user(full_name),
    )
    execution = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED,
        idempotency_key="wf_1",
        material_row_id="44444444-4444-4444-8444-444444444444",
    )
    return InteractionHandled(result=result, reply_text="ok", execution_result=execution)


async def test_advance_does_nothing_when_no_plan_exists():
    store = _plan_store()
    runtime = _FakeWorkflowRuntime([])
    prompt = await advance_member_plan_after_user_created(
        _handled_create_user_success(),
        plan_store=store,
        workflow_runtime=runtime,
        actor=_Actor(),
    )
    assert prompt is None
    assert runtime.start_calls == []


async def test_advance_does_nothing_for_a_confirmation_that_isnt_create_user():
    """A standalone (non-chained) confirmation of anything else must never
    be mistaken for a plan step -- the overwhelmingly common case, and it
    must stay a cheap no-op."""
    store = _plan_store()
    draft = DraftActionV2(
        draft_id="d",
        correlation_id="c",
        workflow_instance_id="w",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=None,
        fields={},
    )
    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="w",
        correlation_id="c",
        confirmed_action=ConfirmedActionV2(
            confirmed_action_id="c1",
            workflow_instance_id="w",
            correlation_id="c",
            draft_action=draft,
            confirmed_by_user_id=USR,
        ),
    )
    execution = ExecutionResult(status=ExecutionStatus.SUCCEEDED, idempotency_key="w", material_row_id="m1")
    handled = InteractionHandled(result=result, reply_text="ok", execution_result=execution)

    runtime = _FakeWorkflowRuntime([])
    prompt = await advance_member_plan_after_user_created(
        handled, plan_store=store, workflow_runtime=runtime, actor=_Actor()
    )
    assert prompt is None
    assert runtime.start_calls == []


async def test_advance_finishes_the_original_request_end_to_end():
    """The full chain: a create_user confirmation completes, the plan
    advances, and ADD_PROJECT_MEMBER starts with member_name resolved to
    the exact name CREATE_USER's own draft confirmed -- never the original
    (possibly mistranslated) name_hint."""
    store = _plan_store()
    create_runtime = _FakeWorkflowRuntime(
        [
            _awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")
        ]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(member_name="Hysam", role="PROJECT_MANAGER"),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=create_runtime,
    )

    resume_runtime = _FakeWorkflowRuntime(
        [
            _started(WorkflowKey.ADD_PROJECT_MEMBER, "Confirm this action?")
        ]
    )
    prompt = await advance_member_plan_after_user_created(
        _handled_create_user_success(full_name="Hisham"),  # the exact created name
        plan_store=store,
        workflow_runtime=resume_runtime,
        actor=_Actor(),
    )

    assert prompt == "Confirm this action?"
    assert len(resume_runtime.start_calls) == 1
    decision, event = resume_runtime.start_calls[0]
    assert decision.workflow_key is WorkflowKey.ADD_PROJECT_MEMBER
    assert decision.project_id == PRJ
    assert event.fields["member_name"] == "Hisham"  # resolved via StepRef, not the name_hint
    assert event.fields["role"] == "PROJECT_MANAGER"
    assert event.fields["created_by_role"] == "PROJECT_MANAGER"

    # The plan is finished and cleared -- ADD_PROJECT_MEMBER now runs as an
    # ordinary, independently-confirmed workflow.
    assert await store.get_plan(user_id=USR) is None


async def test_advance_is_a_no_op_when_the_create_user_step_isnt_running():
    """A CREATE_USER confirmed outside of any plan (the ordinary path) must
    not be mistaken for advancing a stale/foreign plan."""
    store = _plan_store()
    runtime = _FakeWorkflowRuntime(
        [
            _awaiting_input(WorkflowKey.CREATE_USER, "x")
        ]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=runtime,
    )
    # Simulate the create_user step already having completed once (e.g. a
    # duplicate webhook delivery re-triggering this hook).
    await store.mark_step_done(user_id=USR, step_id="create_user", outputs={"user_id": "u1", "full_name": "Hisham"})

    resume_runtime = _FakeWorkflowRuntime([])
    prompt = await advance_member_plan_after_user_created(
        _handled_create_user_success(),
        plan_store=store,
        workflow_runtime=resume_runtime,
        actor=_Actor(),
    )
    assert prompt is None
    assert resume_runtime.start_calls == []


async def test_abandoned_plan_does_not_hijack_a_later_unrelated_create_user():
    """A plan the user walked away from must never attach itself to a
    DIFFERENT CREATE_USER started later inside the plan's TTL.

    The regression: "add Hysam to the hospital project as PM" -> tap "Yes,
    create" -> abandon. Twenty minutes later the same admin legitimately
    adds Rajesh as a site engineer. Matching the waiting plan on
    workflow_key + RUNNING alone made that confirmation look like the one
    the plan was waiting for, and offered *Rajesh* project-manager rights on
    *Hysam's* project.
    """
    store = _plan_store()
    create_runtime = _FakeWorkflowRuntime(
        [_awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(member_name="Hysam", role="PROJECT_MANAGER"),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=create_runtime,
    )
    # The user abandons: the plan is still there, first step still RUNNING.
    stale = await store.get_plan(user_id=USR)
    assert stale is not None
    assert stale.step("create_user").status is StepStatus.RUNNING

    # A completely unrelated CREATE_USER, confirmed successfully.
    other = _handled_create_user_success(full_name="Rajesh")
    other_result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf_some_other_create_user",
        correlation_id="cor_other",
        confirmed_action=other.result.confirmed_action,
    )
    unrelated = InteractionHandled(
        result=other_result, reply_text="ok", execution_result=other.execution_result
    )

    resume_runtime = _FakeWorkflowRuntime([])
    prompt = await advance_member_plan_after_user_created(
        unrelated, plan_store=store, workflow_runtime=resume_runtime, actor=_Actor()
    )

    assert prompt is None
    assert resume_runtime.start_calls == []
    # And the waiting plan is left intact -- an unrelated workflow must not
    # silently cancel it either.
    assert await store.get_plan(user_id=USR) is not None


async def test_rejecting_the_create_user_clears_the_waiting_plan():
    """Saying NO to "create this user?" ends the chain. Otherwise the plan
    lingers for the rest of its TTL with its first step still RUNNING,
    waiting on a confirmation that is never coming."""
    store = _plan_store()
    create_runtime = _FakeWorkflowRuntime(
        [_awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=create_runtime,
    )
    assert await store.get_plan(user_id=USR) is not None

    rejected = InteractionHandled(
        result=WorkflowResumeResult(
            status=WorkflowResumeStatus.REJECTED,
            workflow_instance_id=CREATE_USER_WF,
            correlation_id="cor_cu",
        ),
        reply_text="Discarded.",
    )
    resume_runtime = _FakeWorkflowRuntime([])
    prompt = await advance_member_plan_after_user_created(
        rejected, plan_store=store, workflow_runtime=resume_runtime, actor=_Actor()
    )

    assert prompt is None
    assert resume_runtime.start_calls == []
    assert await store.get_plan(user_id=USR) is None


async def test_rejecting_an_unrelated_create_user_leaves_the_plan_alone():
    """The mirror of the test above: a rejection belonging to some other
    CREATE_USER must not cancel a plan that is still legitimately waiting."""
    store = _plan_store()
    create_runtime = _FakeWorkflowRuntime(
        [_awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=create_runtime,
    )

    rejected_elsewhere = InteractionHandled(
        result=WorkflowResumeResult(
            status=WorkflowResumeStatus.REJECTED,
            workflow_instance_id="wf_some_other_create_user",
            correlation_id="cor_other",
        ),
        reply_text="Discarded.",
    )
    await advance_member_plan_after_user_created(
        rejected_elsewhere,
        plan_store=store,
        workflow_runtime=_FakeWorkflowRuntime([]),
        actor=_Actor(),
    )

    assert await store.get_plan(user_id=USR) is not None


async def test_plan_records_the_started_create_user_instance_id():
    """The guard above is only as good as the id being persisted at all."""
    store = _plan_store()
    runtime = _FakeWorkflowRuntime(
        [_awaiting_input(WorkflowKey.CREATE_USER, "What's their WhatsApp number?")]
    )
    await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=runtime,
    )
    plan = await store.get_plan(user_id=USR)
    assert plan is not None
    assert plan.step("create_user").workflow_instance_id == CREATE_USER_WF


async def test_no_plan_is_left_behind_when_create_user_fails_to_start():
    """A failed start must leave no plan at all -- the plan is persisted
    only after the workflow it tracks actually started."""
    store = _plan_store()

    class _FailingRuntime:
        async def start(self, decision, event):
            raise RuntimeError("boom")

        async def abandon_optional_question(self, user_id: str) -> None:
            return None

    prompt = await start_member_create_plan(
        name_hint="Hysam",
        original_event=_original_event(),
        actor=_Actor(),
        plan_store=store,
        workflow_runtime=_FailingRuntime(),
    )
    assert prompt is None
    assert await store.get_plan(user_id=USR) is None
