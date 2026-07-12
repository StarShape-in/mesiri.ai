"""RecordExpenseHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.fakes import (
    FakeDatabase,
    FakeExpenseCategoryResolver,
    FakeExpenseExecutionRepository,
    PersistSuccessRaisesRepository,
    RejectingExpenseCategoryResolver,
)
from mesiri.application.expenses.handlers import RecordExpenseHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
CAT = "44444444-4444-4444-8444-444444444444"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> RecordExpenseCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        project_id=PRJ,
        category_id=CAT,
        amount=Decimal("250.00"),
        occurred_date=date.today(),
        created_by=USR,
    )
    base.update(overrides)
    return RecordExpenseCommand(**base)


@pytest.mark.asyncio
async def test_valid_command_succeeds_and_persists_one_row():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(repo)

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(repo.expense_rows) == 1


@pytest.mark.asyncio
async def test_invalid_command_is_rejected_without_persisting():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(repo)

    result = await handler.handle(None, _command(amount=Decimal("0")))

    assert result.status == ExecutionStatus.REJECTED
    assert "amount must be greater than zero" in result.rejection_reasons
    assert repo.expense_rows == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_insert():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(repo)

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert second.material_row_id == first.material_row_id
    assert len(repo.expense_rows) == 1


@pytest.mark.asyncio
async def test_repeated_rejection_replays_cached_result():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(repo)
    bad = _command(amount=Decimal("-1"))

    first = await handler.handle(None, bad)
    second = await handler.handle(None, bad)

    assert first.status == second.status == ExecutionStatus.REJECTED
    assert first.rejection_reasons == second.rejection_reasons


@pytest.mark.asyncio
async def test_validation_runs_before_repository_is_asked_to_persist_success():
    """Proves the Handler decides validity itself before touching the
    repository — persist_success is never called for a command the Handler
    already knows is invalid."""
    handler = RecordExpenseHandler(PersistSuccessRaisesRepository())

    result = await handler.handle(None, _command(amount=Decimal("0")))

    assert result.status == ExecutionStatus.REJECTED


@pytest.mark.asyncio
async def test_category_text_is_resolved_when_category_id_absent():
    """WhatsApp-shaped command: no category_id, only free-text category_text —
    the resolver fills it in before persistence."""
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(repo, resolver=FakeExpenseCategoryResolver())

    result = await handler.handle(
        None, _command(category_id=None, category_text="materials")
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert repo.expense_rows[0]["command"].category_id is not None


@pytest.mark.asyncio
async def test_unresolvable_category_text_is_rejected():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(
        repo, resolver=RejectingExpenseCategoryResolver(["category 'nonsense' not found"])
    )

    result = await handler.handle(
        None, _command(category_id=None, category_text="nonsense")
    )

    assert result.status == ExecutionStatus.REJECTED
    assert "category 'nonsense' not found" in result.rejection_reasons
    assert repo.expense_rows == []


@pytest.mark.asyncio
async def test_resolver_is_not_consulted_when_category_id_already_set():
    """REST-shaped command: category_id already known, no resolution needed —
    even a resolver that would reject everything must not be consulted."""
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(
        repo, resolver=RejectingExpenseCategoryResolver(["should never be seen"])
    )

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.RECORD_EXPENSE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=None,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


@pytest.mark.asyncio
async def test_handle_confirmed_maps_and_resolves_then_persists():
    """WhatsApp/CQRS entry point: owns its own transaction, maps the confirmed
    action, resolves free-text category, then persists — end to end."""
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(
        repo, db=FakeDatabase(), resolver=FakeExpenseCategoryResolver()
    )

    result = await handler.handle_confirmed(
        _confirmed({"amount": 250, "category": "materials"})
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.expense_rows) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeExpenseExecutionRepository()
    handler = RecordExpenseHandler(
        repo, db=FakeDatabase(), resolver=FakeExpenseCategoryResolver()
    )
    confirmed = _confirmed({"amount": 250, "category": "materials"})

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.expense_rows) == 1
