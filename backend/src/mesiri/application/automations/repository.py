"""CreateAutomation execution repository port (interface).

Mirrors application/projects/repository.py's CreateSiteExecutionRepository
shape -- the confirmed-message (WhatsApp) write path, distinct from the
dashboard's direct-REST PostgresAutomationRepository (which this still
delegates the actual INSERT to, see infrastructure/postgres/repositories/
automation_execution.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .create_commands import CreateAutomationCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class CreateAutomationExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: CreateAutomationCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and insert the new automation -- against
        `conn`. Assumes cmd is already valid and audience_user_ids is
        already resolved (the Handler is responsible for both before
        calling this)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, idempotency_key: str, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and record a REJECTED result -- no
        automation row is written."""
        ...
