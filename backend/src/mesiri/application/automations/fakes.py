"""In-memory fakes for CreateAutomation application-layer unit tests — no DB, no SQL.

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

from .create_commands import CreateAutomationCommand
from .name_resolution import AudienceNameResolver, NameResolutionResult
from .repository import CreateAutomationExecutionRepository


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL."""

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeCreateAutomationExecutionRepository(CreateAutomationExecutionRepository):
    def __init__(self) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # automations actually "written", for test assertions
        self.automation_writes: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: CreateAutomationCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        row_id = str(uuid.uuid4())
        self.automation_writes.append({"id": row_id, "command": cmd})
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


class FakeAudienceNameResolver(AudienceNameResolver):
    """Resolves names against an in-memory {name (lowercased): user_id} map
    supplied by the test -- unresolved names come back in
    NameResolutionResult.unresolved_names, same contract as the real
    Postgres-backed resolver."""

    def __init__(self, known: dict[str, str] | None = None) -> None:
        self._known = {k.lower(): v for k, v in (known or {}).items()}

    async def resolve(
        self, conn: Any, *, organization_id: str, names: list[str]
    ) -> NameResolutionResult:
        resolved: list[str] = []
        unresolved: list[str] = []
        for name in names:
            user_id = self._known.get(name.strip().lower())
            if user_id is None:
                unresolved.append(name)
            else:
                resolved.append(user_id)
        return NameResolutionResult(resolved_user_ids=resolved, unresolved_names=unresolved)
