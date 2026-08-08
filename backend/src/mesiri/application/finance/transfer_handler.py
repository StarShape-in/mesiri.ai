"""Application Handler for TransferMoney — the WhatsApp/CQRS entry point.

Mirrors application/finance/handlers.py's ManageMoneyAccountHandler.
Orchestration order: pure validate -> check idempotency -> resolve (verify
both accounts still exist and are active) -> persist success or rejection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay

from .transfer_commands import TransferMoneyCommand
from .transfer_mapper import build_command
from .transfer_repository import TransferExecutionRepository
from .transfer_resolution import TransferAccountResolver
from .transfer_validation import validate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2


class TransferMoneyHandler:
    def __init__(
        self,
        repo: TransferExecutionRepository,
        db: PostgresDatabase | None = None,
        resolver: TransferAccountResolver | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._resolver = resolver

    async def handle(self, conn: AsyncConnection, cmd: TransferMoneyCommand) -> ExecutionResult:
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
