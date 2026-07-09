"""Application Handler for confirmed Material actions (M8).

Owns the orchestration order: map -> validate (pure, no transaction) -> open
the one transaction -> check idempotency -> persist success or rejection.
This is the only place a transaction is opened (Requirement 7 — transaction
ownership is centralized here, not scattered across repositories).

FAILED is never constructed here: an unhandled exception from anything below
propagates out of this method, rolling back the transaction (workflow stays
at CONFIRMED, recoverable) — the caller (the interactions ExecutionDispatcher
adapter) is responsible for catching it and reporting ExecutionStatus.FAILED.
"""

from __future__ import annotations

from mesiri.domains.materials import validation
from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .mapper import build_command
from .repository import MaterialExecutionRepository


class ExecuteConfirmedMaterialActionHandler:
    def __init__(self, db: PostgresDatabase, repo: MaterialExecutionRepository) -> None:
        self._db = db
        self._repo = repo

    async def handle(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        cmd = build_command(confirmed)
        reasons = validation.validate(cmd)

        async with self._db.transaction() as conn:
            existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
            if existing is not None:
                return as_replay(existing)

            if reasons:
                return await self._repo.persist_rejection(conn, cmd, reasons)
            return await self._repo.persist_success(conn, cmd)
