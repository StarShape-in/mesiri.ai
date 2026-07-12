"""In-memory ExpenseExecutionRepository for tests — no DB, no SQL.

Mirrors mesiri.application.materials.fakes.FakeMaterialExecutionRepository's style.
"""

from __future__ import annotations

import uuid
from typing import Any

from .commands import RecordExpenseCommand
from .repository import ExpenseExecutionRepository
from .results import ExecutionStatus, ExpenseExecutionResult, as_replay


class FakeExpenseExecutionRepository(ExpenseExecutionRepository):
    def __init__(self) -> None:
        # idempotency_key -> ExpenseExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExpenseExecutionResult] = {}
        # expense rows actually "persisted", for test assertions
        self.expense_rows: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExpenseExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(
        self, conn: Any, cmd: RecordExpenseCommand
    ) -> ExpenseExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        expense_id = str(uuid.uuid4())
        self.expense_rows.append({"id": expense_id, "command": cmd})
        result = ExpenseExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            expense_id=expense_id,
        )
        self._claims[cmd.idempotency_key] = result
        return result

    async def persist_rejection(
        self, conn: Any, cmd: RecordExpenseCommand, reasons: list[str]
    ) -> ExpenseExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        result = ExpenseExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        self._claims[cmd.idempotency_key] = result
        return result


class PersistSuccessRaisesRepository(ExpenseExecutionRepository):
    """persist_success raises; persist_rejection behaves normally — proves the
    Handler never calls persist_success for a command it already knows is invalid."""

    async def check_idempotency(self, conn: Any, key: str) -> ExpenseExecutionResult | None:
        return None

    async def persist_success(
        self, conn: Any, cmd: RecordExpenseCommand
    ) -> ExpenseExecutionResult:
        raise AssertionError("persist_success must not be called for an invalid command")

    async def persist_rejection(
        self, conn: Any, cmd: RecordExpenseCommand, reasons: list[str]
    ) -> ExpenseExecutionResult:
        return ExpenseExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
