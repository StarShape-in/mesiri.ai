"""ReverseTransaction execution repository port.

Mirrors mesiri.application.finance.repository.AccountAdminExecutionRepository.
Every method takes an externally-supplied connection — the WhatsApp/CQRS
handler owns the transaction (see reverse_handler.py's docstring).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .reverse_commands import ReverseTransactionCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class ReverseExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and perform the void/reverse write --
        against `conn`. Assumes cmd is already valid and resolved (the
        Handler is responsible for that before calling this)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and cache REJECTED (no write) — against `conn`."""
        ...
