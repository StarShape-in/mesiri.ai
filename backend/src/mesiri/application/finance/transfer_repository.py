"""TransferMoney execution repository port.

Mirrors mesiri.application.expenses.repository.ExpenseExecutionRepository /
application/finance/repository.py's AccountAdminExecutionRepository. Every
method takes an externally-supplied connection — the WhatsApp/CQRS handler
owns the transaction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .transfer_commands import TransferMoneyCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class TransferExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: TransferMoneyCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and post the transfer ledger entry —
        against `conn`. Assumes cmd is already valid and resolved (the
        Handler is responsible for that before calling this)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: TransferMoneyCommand, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and cache REJECTED (no ledger write) — against `conn`."""
        ...
