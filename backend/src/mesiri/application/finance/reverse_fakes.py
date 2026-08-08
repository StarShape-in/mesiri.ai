"""In-memory ReverseExecutionRepository/ReverseTargetResolver for tests.

Mirrors application/expenses/fakes' style.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)

from .reverse_commands import ReverseTransactionCommand
from .reverse_repository import ReverseExecutionRepository
from .reverse_resolution import ResolutionResult, ReverseTargetResolver


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL. Mirrors
    mesiri.application.expenses.fakes.FakeDatabase."""

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeReverseExecutionRepository(ReverseExecutionRepository):
    def __init__(self) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # reversal writes actually "persisted", for test assertions
        self.reversal_writes: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: ReverseTransactionCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        row_id = str(uuid.uuid4())
        self.reversal_writes.append({"id": row_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=row_id,
        )
        self._claims[cmd.idempotency_key] = result
        return result

    async def persist_rejection(
        self, conn: Any, cmd: ReverseTransactionCommand, reasons: list[str]
    ) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        self._claims[cmd.idempotency_key] = result
        return result


class FakeReverseTargetResolver(ReverseTargetResolver):
    """Always resolves successfully -- no catalog/DB involved."""

    async def resolve(self, conn: Any, cmd: ReverseTransactionCommand) -> ResolutionResult:
        return ResolutionResult(reasons=[])


class RejectingReverseTargetResolver(ReverseTargetResolver):
    """Always rejects with the given reasons — for testing the resolution-failure path."""

    def __init__(self, reasons: list[str]) -> None:
        self._reasons = reasons

    async def resolve(self, conn: Any, cmd: ReverseTransactionCommand) -> ResolutionResult:
        return ResolutionResult(reasons=self._reasons)
