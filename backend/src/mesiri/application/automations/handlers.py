"""Application handler for confirmed (WhatsApp) automation creation.

Mirrors application/projects/handlers.py's CreateSiteHandler shape almost
exactly, with one extra step: `handle()` resolves any audience_names hints
into audience_user_ids (a DB round trip, so it cannot happen in the pure
workflow node -- see workflows/automation_setup/nodes.py's docstring) before
running the ordinary structural validate(). A name that doesn't resolve to
any active org user is a rejection, same "hard rejection, never a silent
default" reasoning application/finance/resolution.py's docstring states for
account names -- proceeding with a partially-resolved audience would
silently drop whoever was misspelled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .create_mapper import build_command
from .create_validation import validate
from .name_resolution import AudienceNameResolver
from .repository import CreateAutomationExecutionRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from .create_commands import CreateAutomationCommand


class CreateAutomationHandler:
    """Confirmed-message (WhatsApp) automation creation. Mirrors
    CreateSiteHandler's handle()/handle_confirmed() split -- handle() takes
    an externally-supplied connection (tests can drive it directly);
    handle_confirmed() is the CQRS entry point that owns the one
    transaction."""

    def __init__(
        self,
        repo: CreateAutomationExecutionRepository,
        name_resolver: AudienceNameResolver,
        db: PostgresDatabase | None = None,
    ) -> None:
        self._repo = repo
        self._name_resolver = name_resolver
        self._db = db

    async def handle(self, conn: AsyncConnection, cmd: CreateAutomationCommand) -> ExecutionResult:
        if cmd.audience == "USERS" and not cmd.audience_user_ids and cmd.audience_names:
            resolution = await self._name_resolver.resolve(
                conn, organization_id=cmd.organization_id, names=cmd.audience_names
            )
            if resolution.unresolved_names:
                names = ", ".join(resolution.unresolved_names)
                reasons = [f"couldn't find an active user named {names}"]
                existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
                if existing is not None:
                    return as_replay(existing)
                return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
            cmd = cmd.model_copy(update={"audience_user_ids": resolution.resolved_user_ids})

        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) -- owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
