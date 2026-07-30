"""Application handler for confirmed (WhatsApp) user creation.

Mirrors application/projects/handlers.py's CreateSiteHandler shape --
handle() takes an externally-supplied connection (tests can drive it
directly); handle_confirmed() is the CQRS entry point that owns the one
transaction. No name-resolution step here (unlike AddProjectMemberHandler)
-- CREATE_USER always makes a brand new row, there is nothing to look up
first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_user_mapper import build_command
from .create_user_validation import validate
from .repository import CreateUserExecutionRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from .create_user_commands import CreateUserCommand


class CreateUserHandler:
    """Confirmed-message (WhatsApp) user creation. Mirrors
    application/projects/handlers.py's CreateSiteHandler exactly."""

    def __init__(
        self,
        repo: CreateUserExecutionRepository,
        db: PostgresDatabase | None = None,
    ) -> None:
        self._repo = repo
        self._db = db

    async def handle(self, conn: AsyncConnection, cmd: CreateUserCommand) -> ExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
