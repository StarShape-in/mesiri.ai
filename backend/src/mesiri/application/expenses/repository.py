"""RecordExpense execution repository port.

Mirrors mesiri.application.materials.repository.MaterialExecutionRepository.
Every method takes an externally-supplied connection. Unlike Materials'
CQRS path, RecordExpense has no workflow_instances row to transition (there
is no WhatsApp/Planner confirmation step yet — see commands.py) and no
Handler-owned transaction: the REST router's `get_db_conn` dependency already
runs the whole request inside one transaction, so the repository writes
directly against the connection it is given.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .commands import RecordExpenseCommand
from .results import ExpenseExecutionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class ExpenseExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(
        self, conn: AsyncConnection, key: str
    ) -> ExpenseExecutionResult | None:
        """Return the cached ExpenseExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: RecordExpenseCommand
    ) -> ExpenseExecutionResult:
        """Claim the idempotency key and insert the expense row — against `conn`."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: RecordExpenseCommand, reasons: list[str]
    ) -> ExpenseExecutionResult:
        """Claim the idempotency key and cache REJECTED (no expense row) — against `conn`."""
        ...
