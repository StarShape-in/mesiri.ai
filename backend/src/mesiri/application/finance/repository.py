"""ManageMoneyAccount execution repository port.

Mirrors mesiri.application.expenses.repository.ExpenseExecutionRepository.
Every method takes an externally-supplied connection — the WhatsApp/CQRS
handler owns the transaction (see handlers.py's docstring); there is no REST
entry point for this command in this phase, so unlike expenses there is no
second caller supplying its own connection today.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .commands import ManageMoneyAccountCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class AccountAdminExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: ManageMoneyAccountCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and perform the create/rename/deactivate
        write — against `conn`. Assumes cmd is already valid and resolved
        (target_account_id set for rename/deactivate) — the Handler is
        responsible for that before calling this."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: ManageMoneyAccountCommand, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and cache REJECTED (no account write) — against `conn`."""
        ...
