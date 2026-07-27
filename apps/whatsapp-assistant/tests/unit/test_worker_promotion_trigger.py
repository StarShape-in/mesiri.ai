"""_maybe_trigger_worker_promotion (runtime/inbound_journey.py) -- unit tests.

Covers the extraction/filtering logic that decides which confirmed attendance
lines are offered for promotion: named + never matched to a registered
worker. Headcount-only lines and already-matched lines must never reach the
offer, per the plan's rule that promotion applies only to named workers who
are new.

Uses a fake WorkflowRuntime.start() so these stay fast, isolated unit tests;
the real LangGraph executor-thread boundary is covered separately in
tests/integration/test_worker_promotion_graph.py.
"""

from __future__ import annotations

import uuid

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.inbound_journey import _maybe_trigger_worker_promotion
from workflows.runtime import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult

ORG = str(uuid.uuid4())
USR = str(uuid.uuid4())
PRJ = str(uuid.uuid4())
RAVI_ID = str(uuid.uuid4())


def _confirmed(lines: list[dict]) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft1",
        correlation_id="cor1",
        workflow_instance_id="wf1",
        action_type=DraftActionType.RECORD_LABOUR_ATTENDANCE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields={"lines": lines},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf1",
        workflow_instance_id="wf1",
        correlation_id="cor1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def _handled(lines: list[dict], *, succeeded: bool = True):
    from interactions.handler import InteractionHandled

    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf1",
        correlation_id="cor1",
        confirmed_action=_confirmed(lines),
    )
    execution_result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED if succeeded else ExecutionStatus.FAILED,
        idempotency_key="idem1",
        material_row_id="row1" if succeeded else None,
    )
    return InteractionHandled(result=result, reply_text="ok", execution_result=execution_result)


class _FakeActor:
    def __init__(self) -> None:
        self.organization_id = ORG
        self.user_id = USR


class _FakeWorkforceQuery:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.candidates: list[dict] = []

    async def list_worker_candidates(self, **kwargs):
        return self.candidates

    async def create_worker(self, **kwargs):
        self.created.append(kwargs)
        return "new-id"


class _FakeWorkflowRuntime:
    """Records the decision/event it was asked to start; never runs a graph."""

    def __init__(self, pending_prompt: str | None = "offer sent") -> None:
        self.started_with: tuple | None = None
        self._pending_prompt = pending_prompt

    async def start(self, decision, event):
        self.started_with = (decision, event)
        return WorkflowRunResult.awaiting_input(
            workflow_key=WorkflowKey.WORKER_PROMOTION,
            correlation_id=event.correlation_id,
            workflow_instance_id="wf_promo",
            pending_prompt=self._pending_prompt,
        )


async def _send_text_recorder():
    sent: list[tuple[str, str]] = []

    async def send_text(wa_id: str, text: str):
        sent.append((wa_id, text))

    return sent, send_text


async def test_only_named_unmatched_lines_are_offered():
    """Headcount-only lines ("12 helpers") have nobody to promote, and a line
    already matched to a registered worker is by definition not new."""
    handled = _handled(
        [
            {"worker_name": "Ravi", "trade": "mason", "worker_id": None, "daily_wage": "800"},
            {"worker_name": None, "trade": "helper", "headcount": 12, "worker_id": None},
            {"worker_name": "Suresh", "trade": "painter", "worker_id": RAVI_ID},
        ]
    )
    runtime = _FakeWorkflowRuntime()
    workforce_query = _FakeWorkforceQuery()
    sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, workforce_query, _FakeActor(), "wa123", send_text
    )

    assert runtime.started_with is not None
    _decision, event = runtime.started_with
    promotable = event.fields["promotable_workers"]
    assert [w["name"] for w in promotable] == ["Ravi"]


async def test_the_register_is_seeded_for_the_duplicate_check():
    """The node must never query a repository itself, so the register it
    screens against has to arrive in the event fields."""
    handled = _handled([{"worker_name": "Ravi", "trade": "mason", "worker_id": None}])
    runtime = _FakeWorkflowRuntime()
    workforce_query = _FakeWorkforceQuery()
    workforce_query.candidates = [
        {"worker_id": "w1", "name": "Ravi Kumar", "trade": "mason", "contractor": None}
    ]
    _sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, workforce_query, _FakeActor(), "wa123", send_text
    )

    _decision, event = runtime.started_with
    assert event.fields["_register"] == workforce_query.candidates


async def test_a_failing_register_read_never_blocks_the_promotion_offer():
    """Attendance is already saved. If the register read fails, offering
    promotion without the duplicate screen still beats offering nothing."""

    class _BrokenQuery(_FakeWorkforceQuery):
        async def list_worker_candidates(self, **kwargs):
            raise RuntimeError("db down")

    handled = _handled([{"worker_name": "Ravi", "trade": "mason", "worker_id": None}])
    runtime = _FakeWorkflowRuntime()
    _sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, _BrokenQuery(), _FakeActor(), "wa123", send_text
    )

    _decision, event = runtime.started_with
    assert event.fields["_register"] == []


async def test_no_named_new_workers_never_starts_the_promotion_workflow():
    handled = _handled(
        [{"worker_name": None, "trade": "helper", "headcount": 12, "worker_id": None}]
    )
    runtime = _FakeWorkflowRuntime()
    _sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, _FakeWorkforceQuery(), _FakeActor(), "wa123", send_text
    )

    assert runtime.started_with is None


async def test_failed_execution_never_triggers_promotion():
    handled = _handled(
        [{"worker_name": "Ravi", "trade": "mason", "worker_id": None}], succeeded=False
    )
    runtime = _FakeWorkflowRuntime()
    _sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, _FakeWorkforceQuery(), _FakeActor(), "wa123", send_text
    )

    assert runtime.started_with is None


async def test_the_offer_message_is_sent_to_the_reporting_user():
    handled = _handled([{"worker_name": "Ravi", "trade": "mason", "worker_id": None}])
    runtime = _FakeWorkflowRuntime(pending_prompt="I found these new named workers")
    sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, runtime, _FakeWorkforceQuery(), _FakeActor(), "wa123", send_text
    )

    assert sent == [("wa123", "I found these new named workers")]


async def test_promotion_start_failure_never_raises():
    """Promotion is a courtesy follow-up -- attendance is already confirmed
    and saved by the time this runs, so a failure here must never surface as
    an error to the user or block anything upstream."""

    class _BrokenRuntime:
        async def start(self, decision, event):
            raise RuntimeError("boom")

    handled = _handled([{"worker_name": "Ravi", "trade": "mason", "worker_id": None}])
    _sent, send_text = await _send_text_recorder()

    await _maybe_trigger_worker_promotion(
        handled, _BrokenRuntime(), _FakeWorkforceQuery(), _FakeActor(), "wa123", send_text
    )
