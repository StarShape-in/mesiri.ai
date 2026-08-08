"""ExecuteConfirmedLabourAttendanceHandler — unit tests (fakes only, no DB).

Mirrors test_material_execution_handler.py's structure. No resolver here,
unlike materials — Labour has nothing to resolve at execution time (worker
matching already happened in the workflow before confirmation).
"""

from __future__ import annotations

from mesiri.application.labour.fakes import (
    FakeDatabase,
    FakeLabourExecutionRepository,
    PersistSuccessRaisesRepository,
)
from mesiri.application.labour.handlers import ExecuteConfirmedLabourAttendanceHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"
WF_ID = "55555555-5555-4555-8555-555555555555"


def _confirmed(fields: dict, *, project_id=PRJ) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id=WF_ID,
        action_type=DraftActionType.RECORD_LABOUR_ATTENDANCE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id=WF_ID,
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def _seeded_workflow_repo(confirmed: ConfirmedActionV2) -> FakeWorkflowInstanceRepository:
    repo = FakeWorkflowInstanceRepository()
    state = WorkflowStateV2(
        workflow_instance_id=confirmed.workflow_instance_id,
        workflow_key=WorkflowKey.LABOUR_ATTENDANCE,
        correlation_id=confirmed.correlation_id,
        organization_id=ORG,
        user_id=USR,
        project_id=confirmed.draft_action.project_id,
        phase=WorkflowPhase.CONFIRMED,
        draft_action=confirmed.draft_action,
    )
    repo.seed(state, version=1)  # version 1: already bumped once by M7's own confirm
    return repo


_LINES = {"lines": [{"worker_name": "Ravi", "trade": "mason", "headcount": 1}]}


async def test_success():
    confirmed = _confirmed(_LINES)
    workflow_repo = _seeded_workflow_repo(confirmed)
    labour_repo = FakeLabourExecutionRepository(workflow_repo=workflow_repo)
    handler = ExecuteConfirmedLabourAttendanceHandler(db=FakeDatabase(), repo=labour_repo)

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(labour_repo.reports) == 1
    assert labour_repo.reports[0]["command"].lines[0].worker_name == "Ravi"
    saved_state, _ = workflow_repo._rows[WF_ID]  # noqa: SLF001 — test assertion
    assert saved_state.phase is WorkflowPhase.COMPLETED


async def test_validation_rejection_transitions_to_execution_rejected_not_confirmed():
    """Same regression the materials handler guards against: a business-rule
    rejection must move the workflow to EXECUTION_REJECTED, not leave it
    stuck at CONFIRMED forever."""
    confirmed = _confirmed(_LINES, project_id=None)  # triggers "project is not resolved"
    workflow_repo = _seeded_workflow_repo(confirmed)
    labour_repo = FakeLabourExecutionRepository(workflow_repo=workflow_repo)
    handler = ExecuteConfirmedLabourAttendanceHandler(db=FakeDatabase(), repo=labour_repo)

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.REJECTED
    assert "project is not resolved" in result.rejection_reasons
    assert labour_repo.reports == []

    saved_state, _ = workflow_repo._rows[WF_ID]  # noqa: SLF001 — test assertion
    assert saved_state.phase is WorkflowPhase.EXECUTION_REJECTED
    assert saved_state.phase is not WorkflowPhase.CONFIRMED


async def test_an_empty_attendance_is_rejected_not_persisted():
    confirmed = _confirmed({})  # no lines at all
    workflow_repo = _seeded_workflow_repo(confirmed)
    labour_repo = FakeLabourExecutionRepository(workflow_repo=workflow_repo)
    handler = ExecuteConfirmedLabourAttendanceHandler(db=FakeDatabase(), repo=labour_repo)

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.REJECTED
    assert "attendance must have at least one line" in result.rejection_reasons


async def test_repeated_rejection_returns_cached_result_without_rerunning_validation():
    confirmed = _confirmed(_LINES, project_id=None)
    workflow_repo = _seeded_workflow_repo(confirmed)
    labour_repo = FakeLabourExecutionRepository(workflow_repo=workflow_repo)
    handler = ExecuteConfirmedLabourAttendanceHandler(db=FakeDatabase(), repo=labour_repo)

    first = await handler.handle(confirmed)
    second = await handler.handle(confirmed)

    assert first.status is ExecutionStatus.REJECTED
    assert second.status is ExecutionStatus.REJECTED
    assert second.rejection_reasons == first.rejection_reasons


async def test_duplicate_execution_second_call_is_already_executed():
    """Idempotency: replaying the same confirmation (e.g. crash recovery) must
    never create a second attendance report."""
    confirmed = _confirmed(_LINES)
    workflow_repo = _seeded_workflow_repo(confirmed)
    labour_repo = FakeLabourExecutionRepository(workflow_repo=workflow_repo)
    handler = ExecuteConfirmedLabourAttendanceHandler(db=FakeDatabase(), repo=labour_repo)

    first = await handler.handle(confirmed)
    second = await handler.handle(confirmed)

    assert first.status is ExecutionStatus.SUCCEEDED
    assert second.status is ExecutionStatus.ALREADY_EXECUTED
    assert second.material_row_id == first.material_row_id
    assert len(labour_repo.reports) == 1  # no second insert


async def test_validation_runs_before_any_repo_persist_call():
    """Proves the Handler decides validity itself and never asks the repo to
    persist a success for an invalid command."""
    confirmed = _confirmed(_LINES, project_id=None)
    handler = ExecuteConfirmedLabourAttendanceHandler(
        db=FakeDatabase(), repo=PersistSuccessRaisesRepository()
    )

    result = await handler.handle(confirmed)  # would raise if persist_success were called

    assert result.status is ExecutionStatus.REJECTED
