"""Application Handler for RecordExpense (narrow REST scope).

Orchestration order: pure validate -> check idempotency -> persist success or
rejection. Unlike Materials' ExecuteConfirmedMaterialActionHandler, this
Handler does not open its own transaction — the caller (the REST router, via
`get_db_conn`) already supplies a connection scoped to one request
transaction. See repository.py's docstring for why.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .commands import RecordExpenseCommand
from .repository import ExpenseExecutionRepository
from .results import ExpenseExecutionResult, as_replay
from .validation import validate

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class RecordExpenseHandler:
    def __init__(self, repo: ExpenseExecutionRepository) -> None:
        self._repo = repo

    async def handle(
        self, conn: AsyncConnection, cmd: RecordExpenseCommand
    ) -> ExpenseExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd, reasons)
        return await self._repo.persist_success(conn, cmd)
