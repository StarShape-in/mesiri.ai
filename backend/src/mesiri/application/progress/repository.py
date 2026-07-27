"""Progress execution repository port (Daily Reporting).

Defines the contract for persisting confirmed Progress commands without
coupling to a specific implementation (PostgreSQL, fake, etc.). Mirrors
application/labour/repository.py and application/materials/repository.py:
every method takes an externally-supplied connection — the repository never
opens an engine and never commits; the Application Handler owns the one
transaction.

Two success-persist methods, not one, matching the two commands this module
has (create vs continue) — see mesiri_contracts.application.commands.progress
for why they are not merged into a single shape. `persist_rejection` is
shared because rejecting either command is the same act: cache the outcome,
transition the workflow, write nothing to the Activity/Progress Update
tables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.commands.progress import (
    AddProgressUpdateCommand,
    CreateActivityCommand,
)
from mesiri_contracts.application.results.execution_result import ExecutionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class ProgressExecutionRepository(ABC):
    """Persists Progress command execution outcomes against a supplied connection."""

    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_create_activity_success(
        self, conn: AsyncConnection, cmd: CreateActivityCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, insert the activity + quantities + outbox
        event, cache SUCCEEDED, and transition the workflow to COMPLETED."""
        ...

    @abstractmethod
    async def persist_add_progress_update_success(
        self, conn: AsyncConnection, cmd: AddProgressUpdateCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, append the progress update + outbox
        event, cache SUCCEEDED, and transition the workflow to COMPLETED.
        Never edits the parent Activity or any prior update (P1)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self,
        conn: AsyncConnection,
        idempotency_key: str,
        command_type: str,
        reasons: list[str],
    ) -> ExecutionResult:
        """Claim the idempotency key, cache REJECTED (no rows written), and
        transition the workflow to EXECUTION_REJECTED."""
        ...
