"""Worker promotion driven through the *real* runtime, registry and graph.

Every other promotion test substitutes a fake WorkflowRuntime, so none of
them ever executed WorkflowRuntime.start() for the promotion workflow --
which is where the offer is actually produced and persisted. That gap is why
the offer has stopped arriving twice for reasons no test noticed.

This drives the real chain: _maybe_trigger_worker_promotion -> real
WorkflowRuntime -> real WorkflowRegistry -> real compiled graph -> real
WorkflowStateV2 persistence, with fakes only at the database and the
WhatsApp sender.
"""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.application.results.execution_result import (  # noqa: E402
    ExecutionResult,
    ExecutionStatus,
)
from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from mesiri_contracts.assistant.planner_decision import WorkflowKey  # noqa: E402
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2  # noqa: E402
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2  # noqa: E402
from mesiri_contracts.context.enums import WorkflowPhase  # noqa: E402
from runtime.inbound_journey import _maybe_trigger_worker_promotion  # noqa: E402
from workflows.fakes import FakeWorkflowInstanceRepository  # noqa: E402
from workflows.registry import WorkflowRegistry  # noqa: E402
from workflows.runtime import (  # noqa: E402
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRuntime,
)

ORG = str(uuid.uuid4())
USR = str(uuid.uuid4())
PRJ = str(uuid.uuid4())
KNOWN_WORKER = str(uuid.uuid4())


class _Actor:
    organization_id = ORG
    user_id = USR


class _Workforce:
    """Register reads/writes, recorded. Empty register unless told otherwise."""

    def __init__(self, register: list[dict] | None = None) -> None:
        self.register = register or []
        self.created: list[dict] = []

    async def list_worker_candidates(self, **kwargs):
        return self.register

    async def create_worker(self, **kwargs):
        self.created.append(kwargs)
        return str(uuid.uuid4())


def _handled(lines: list[dict]):
    from interactions.handler import InteractionHandled

    draft = DraftActionV2(
        draft_id="draft1",
        correlation_id="cor1",
        workflow_instance_id=str(uuid.uuid4()),
        action_type=DraftActionType.RECORD_LABOUR_ATTENDANCE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields={"lines": lines},
    )
    return InteractionHandled(
        result=WorkflowResumeResult(
            status=WorkflowResumeStatus.CONFIRMED,
            workflow_instance_id=draft.workflow_instance_id,
            correlation_id="cor1",
            confirmed_action=ConfirmedActionV2(
                confirmed_action_id=str(uuid.uuid4()),
                workflow_instance_id=draft.workflow_instance_id,
                correlation_id="cor1",
                draft_action=draft,
                confirmed_by_user_id=USR,
            ),
        ),
        reply_text="Recorded.",
        execution_result=ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=draft.workflow_instance_id,
            material_row_id="row1",
        ),
    )


def _sender():
    sent: list[str] = []

    async def send_text(_wa_id: str, text: str) -> None:
        sent.append(text)

    return sent, send_text


def _runtime(repo: FakeWorkflowInstanceRepository) -> WorkflowRuntime:
    return WorkflowRuntime(registry=WorkflowRegistry(), repo=repo)


NEW_TWO = [
    {"worker_name": "Rahul", "trade": "helper", "worker_id": None, "daily_wage": "600"},
    {"worker_name": "Niyas", "trade": "mason", "worker_id": None, "daily_wage": "800"},
    {"worker_name": "Ilan Usman", "trade": "carpenter", "worker_id": KNOWN_WORKER},
    {"worker_name": None, "trade": "helper", "headcount": 12, "worker_id": None},
]


async def test_the_offer_actually_reaches_the_user():
    """The single assertion every earlier test was missing: a real runtime
    run produces a real message."""
    repo = FakeWorkflowInstanceRepository()
    sent, send_text = _sender()

    await _maybe_trigger_worker_promotion(
        _handled(NEW_TWO), _runtime(repo), _Workforce(), _Actor(), "wa1", send_text
    )

    assert len(sent) == 1, f"expected one offer, got {sent}"
    assert "Rahul" in sent[0]
    assert "Niyas" in sent[0]
    # Already registered, and headcount groups, are never offered.
    assert "Ilan Usman" not in sent[0]
    assert "12" not in sent[0]


async def test_the_offer_is_persisted_so_the_reply_can_find_it():
    """An offer nobody can answer is not an offer. The row has to land in
    COLLECTING_FIELDS or get_awaiting_input() will never see the reply."""
    repo = FakeWorkflowInstanceRepository()
    _sent, send_text = _sender()

    await _maybe_trigger_worker_promotion(
        _handled(NEW_TWO), _runtime(repo), _Workforce(), _Actor(), "wa1", send_text
    )

    pending = await repo.get_awaiting_input(USR)
    assert pending is not None, "the offer was never persisted"
    assert pending.state.workflow_key is WorkflowKey.WORKER_PROMOTION
    assert pending.state.awaiting_slot == "promotion_choice"


async def test_a_second_report_replaces_the_first_offer():
    """Reported: a later report's new worker never appeared. Two offers open
    at once means the reply answers whichever is newest while the older list
    is still on screen."""
    repo = FakeWorkflowInstanceRepository()
    sent, send_text = _sender()
    runtime = _runtime(repo)

    await _maybe_trigger_worker_promotion(
        _handled(NEW_TWO), runtime, _Workforce(), _Actor(), "wa1", send_text
    )
    await _maybe_trigger_worker_promotion(
        _handled([{"worker_name": "Ajith", "trade": "painter", "worker_id": None}]),
        runtime,
        _Workforce(),
        _Actor(),
        "wa1",
        send_text,
    )

    assert len(sent) == 2
    assert "Ajith" in sent[1]
    assert "Rahul" not in sent[1], "the second offer must describe the second report"

    open_rows = [
        s
        for s, _v in repo._rows.values()  # noqa: SLF001 — test introspection
        if s.phase is WorkflowPhase.COLLECTING_FIELDS
    ]
    assert len(open_rows) == 1, "exactly one offer may be open at a time"
    assert "Ajith" in str(open_rows[0].collected_fields)


async def test_a_report_with_no_new_named_workers_sends_nothing():
    repo = FakeWorkflowInstanceRepository()
    sent, send_text = _sender()

    await _maybe_trigger_worker_promotion(
        _handled(
            [
                {"worker_name": "Ilan Usman", "trade": "carpenter", "worker_id": KNOWN_WORKER},
                {"worker_name": None, "trade": "helper", "headcount": 12, "worker_id": None},
            ]
        ),
        _runtime(repo),
        _Workforce(),
        _Actor(),
        "wa1",
        send_text,
    )

    assert sent == []
    assert await repo.get_awaiting_input(USR) is None
