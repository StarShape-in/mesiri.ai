"""RecordExpenseHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.fakes import (
    FakeExpenseExecutionRepository,
    PersistSuccessRaisesRepository,
)
from mesiri.application.expenses.handlers import RecordExpenseHandler
from mesiri.application.expenses.results import ExecutionStatus

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
    assert result.expense_id is not None
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
    assert second.expense_id == first.expense_id
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
