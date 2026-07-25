"""In-memory TransferExecutionRepository/TransferAccountResolver for tests.

Mirrors application/finance/fakes.py's style.
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

from .transfer_commands import TransferMoneyCommand
from .transfer_repository import TransferExecutionRepository
from .transfer_resolution import ResolutionResult, TransferAccountResolver


class FakeDatabase:
    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeTransferExecutionRepository(TransferExecutionRepository):
    def __init__(self) -> None:
        self._claims: dict[str, ExecutionResult] = {}
        self.ledger_writes: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: TransferMoneyCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        transaction_id = str(uuid.uuid4())
        self.ledger_writes.append({"id": transaction_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=transaction_id,
        )
        self._claims[cmd.idempotency_key] = result
        return result

    async def persist_rejection(
        self, conn: Any, cmd: TransferMoneyCommand, reasons: list[str]
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


class FakeTransferAccountResolver(TransferAccountResolver):
    """Always resolves successfully -- no catalog/DB involved."""

    async def resolve(self, conn: Any, cmd: TransferMoneyCommand) -> ResolutionResult:
        return ResolutionResult(reasons=[])


class RejectingTransferAccountResolver(TransferAccountResolver):
    def __init__(self, reasons: list[str]) -> None:
        self._reasons = reasons

    async def resolve(self, conn: Any, cmd: TransferMoneyCommand) -> ResolutionResult:
        return ResolutionResult(reasons=self._reasons)
