"""CreateUser execution repository port (interface).

Mirrors application/projects/repository.py's
AddProjectMemberExecutionRepository shape -- the confirmed-message
(WhatsApp) write path, distinct from the dashboard's direct-REST
users/router.py create_user endpoint.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .create_user_commands import CreateUserCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class CreateUserExecutionRepository(ABC):
    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: CreateUserCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and insert the new user -- against
        `conn`. Assumes cmd is already valid (the Handler is responsible
        for that before calling this). Rejects (does not raise) if
        cmd.whatsapp_number is already registered to another user -- it may
        have been registered between draft-build and confirmation."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, idempotency_key: str, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and record a REJECTED result -- no
        user row is written."""
        ...
