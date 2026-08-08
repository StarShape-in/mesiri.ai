"""Labour attendance execution repository port (M8).

Defines the contract for persisting a confirmed RecordLabourAttendanceCommand
without coupling to a specific implementation (PostgreSQL, fake, etc.).
Mirrors application/materials/repository.py exactly: every method takes an
externally-supplied connection — the repository never opens an engine and
never commits; the Application Handler owns the one transaction (backend
capability-boundary + transaction-ownership rules).

Two methods only, not three: unlike Material, Labour attendance is never
rejected by a resolver against a catalog (there is no catalog to resolve
against — worker matching already happened in the workflow before
confirmation). Domain validation failures still go through persist_rejection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.commands.labour import RecordLabourAttendanceCommand
from mesiri_contracts.application.results.execution_result import ExecutionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class LabourExecutionRepository(ABC):
    """Persists Labour attendance command execution outcomes against a supplied connection."""

    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: RecordLabourAttendanceCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, insert the report + lines + attachments +
        outbox event, cache SUCCEEDED, and transition the workflow to
        COMPLETED — all against `conn`."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, cmd: RecordLabourAttendanceCommand, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key, cache REJECTED (no attendance rows), and
        transition the workflow to EXECUTION_REJECTED — all against `conn`."""
        ...
