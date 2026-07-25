"""Application Handler for ManageMoneyAccount — the WhatsApp/CQRS entry point.

Mirrors application/expenses/handlers.py's RecordExpenseHandler, minus the
REST path (there is no REST entry point for this command in this phase, see
docs/execution/FINANCE_MODULE_PLAN.md). Orchestration order: pure validate
-> check idempotency -> resolve target_account_id / duplicate-name check
(resolver) -> persist success or rejection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay

from .commands import ManageMoneyAccountCommand
from .mapper import build_command
from .repository import AccountAdminExecutionRepository
from .resolution import AccountLookupResolver
from .validation import validate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2


class ManageMoneyAccountHandler:
    def __init__(
        self,
        repo: AccountAdminExecutionRepository,
        db: PostgresDatabase | None = None,
        resolver: AccountLookupResolver | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._resolver = resolver

    async def handle(
        self, conn: AsyncConnection, cmd: ManageMoneyAccountCommand
    ) -> ExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if not reasons and self._resolver is not None:
            resolved = await self._resolver.resolve(conn, cmd)
            reasons = resolved.reasons
            if not reasons and resolved.target_account_id is not None:
                cmd = cmd.model_copy(update={"target_account_id": str(resolved.target_account_id)})

        if reasons:
            return await self._repo.persist_rejection(conn, cmd, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
