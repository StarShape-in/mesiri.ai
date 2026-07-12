"""RecordExpense execution repository port.

Mirrors mesiri.application.materials.repository.MaterialExecutionRepository.
Every method takes an externally-supplied connection — neither entry point
(REST's `handle(conn, cmd)` nor the WhatsApp/CQRS `handle_confirmed`) lets
the repository open its own transaction; see handlers.py's docstring for how
the two paths differ in who supplies that connection.

On the WhatsApp/CQRS path, persist_success/persist_rejection also transition
the originating workflow_instances row (COMPLETED/EXECUTION_REJECTED) on the
same connection, mirroring Materials. On the REST path there is no
workflow_instances row for this idempotency_key, so that transition is a
no-op (see infrastructure/postgres/repositories/expense_execution.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .commands import RecordExpenseCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class ExpenseExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: RecordExpenseCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and insert the expense row — against `conn`."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: RecordExpenseCommand, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and cache REJECTED (no expense row) — against `conn`."""
        ...
