"""Application Handler for RecordExpense — serves both entry points.

`handle(conn, cmd)`: the REST path (domains/expenses/router.py). The caller
already supplies a connection scoped to one request transaction (via
`get_db_conn`), so this method never opens its own — see repository.py's
docstring.

`handle_confirmed(confirmed)`: the WhatsApp/CQRS path (M8-style, mirrors
Materials' ExecuteConfirmedMaterialActionHandler.handle()). Owns its own
transaction via `self._db`, maps the confirmed action into a Command, then
delegates to `handle()` so both entry points share the exact same
idempotency/resolution/persistence orchestration.

Orchestration order: pure validate -> check idempotency -> resolve
category_text (only when category_id wasn't already supplied) -> resolve
vendor_text (only when vendor_id wasn't already supplied) -> persist
success or rejection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri.application.vendors.resolution import VendorResolver
from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay

from .commands import RecordExpenseCommand
from .mapper import build_command
from .repository import ExpenseExecutionRepository
from .resolution import ExpenseCategoryResolver
from .validation import validate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2


class RecordExpenseHandler:
    def __init__(
        self,
        repo: ExpenseExecutionRepository,
        db: PostgresDatabase | None = None,
        resolver: ExpenseCategoryResolver | None = None,
        vendor_resolver: VendorResolver | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._resolver = resolver
        self._vendor_resolver = vendor_resolver

    async def handle(self, conn: AsyncConnection, cmd: RecordExpenseCommand) -> ExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if not reasons and cmd.category_id is None and self._resolver is not None:
            resolved = await self._resolver.resolve(conn, cmd)
            reasons = resolved.reasons
            if not reasons:
                cmd = cmd.model_copy(update={"category_id": str(resolved.category_id)})

        if not reasons and cmd.vendor_id is None and self._vendor_resolver is not None:
            vendor_resolved = await self._vendor_resolver.resolve(conn, cmd)
            if vendor_resolved.vendor_id is not None:
                cmd = cmd.model_copy(update={"vendor_id": str(vendor_resolved.vendor_id)})

        if reasons:
            return await self._repo.persist_rejection(conn, cmd, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
