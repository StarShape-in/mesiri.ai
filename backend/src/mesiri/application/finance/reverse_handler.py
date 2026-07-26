"""Application Handler for ReverseTransaction — the WhatsApp/CQRS entry point.

Mirrors application/finance/transfer_handler.py. Orchestration order: pure
validate -> check idempotency -> resolve (re-verify the target still exists
and hasn't already been reversed/voided) -> persist success or rejection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay

from .reverse_commands import ReverseTransactionCommand
from .reverse_mapper import build_command
from .reverse_repository import ReverseExecutionRepository
from .reverse_resolution import ReverseTargetResolver
from .reverse_validation import validate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2


class ReverseTransactionHandler:
    def __init__(
        self,
        repo: ReverseExecutionRepository,
        db: PostgresDatabase | None = None,
        resolver: ReverseTargetResolver | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._resolver = resolver

    async def handle(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if not reasons and self._resolver is not None:
            resolved = await self._resolver.resolve(conn, cmd)
            reasons = resolved.reasons

        if reasons:
            return await self._repo.persist_rejection(conn, cmd, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
