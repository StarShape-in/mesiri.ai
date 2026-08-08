"""In-memory fakes for CreateUser application-layer unit tests — no DB, no SQL.

Mirrors application/projects/fakes.py's FakeCreateSiteExecutionRepository/
FakeDatabase shape.
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

from .create_user_commands import CreateUserCommand
from .repository import CreateUserExecutionRepository


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL."""

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeCreateUserExecutionRepository(CreateUserExecutionRepository):
    def __init__(self) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # users actually "written", for test assertions
        self.user_writes: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: CreateUserCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        row_id = str(uuid.uuid4())
        self.user_writes.append({"id": row_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=row_id,
        )
        self._claims[cmd.idempotency_key] = result
        return result

    async def persist_rejection(
        self, conn: Any, idempotency_key: str, reasons: list[str]
    ) -> ExecutionResult:
        if idempotency_key in self._claims:
            return as_replay(self._claims[idempotency_key])

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=idempotency_key,
            rejection_reasons=reasons,
        )
        self._claims[idempotency_key] = result
        return result
