"""PostgreSQL implementation of mesiri.application.finance.transfer_repository.TransferExecutionRepository.

Only file permitted to hold SQL for TransferMoney execution
(capability-boundary convention, mirrors expense_execution.py /
account_admin_execution.py). Posts a single money_transactions row
(transaction_type='transfer', both from_account_id and to_account_id set)
by composing PostgresMoneyTransactionRepository.record() rather than
inlining new ledger SQL here -- same reasoning as expense_execution.py's use
of PostgresExpensePaymentRepository. get_balance()'s existing
opening_balance + inflow(to) - outflow(from) formula (Slice 0) needs no
changes to reflect a transfer correctly.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa

from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_repository import TransferExecutionRepository
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyTransactionRepository
from mesiri.infrastructure.postgres.workflow_instance import (
    get_by_id_on_connection,
    transition_on_connection,
)
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

_COMMAND_TYPE = "transfer_money"


class PostgresTransferExecutionRepository(TransferExecutionRepository):
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        row = (
            await conn.execute(
                sa.text("SELECT status, result FROM idempotency_keys WHERE key = :key"),
                {"key": key},
            )
        ).mappings().first()
        if row is None or row["status"] != "completed" or row["result"] is None:
            return None
        result_json = row["result"]
        if not isinstance(result_json, str):
            result_json = json.dumps(result_json)
        return ExecutionResult.model_validate_json(result_json)

    async def _try_claim(self, conn: AsyncConnection, cmd: TransferMoneyCommand) -> bool:
        """INSERT ... ON CONFLICT DO NOTHING — True if this call won the claim."""
        claimed = (
            await conn.execute(
                sa.text(
                    "INSERT INTO idempotency_keys (key, command_type, status) "
                    "VALUES (:key, :command_type, 'in_progress') "
                    "ON CONFLICT (key) DO NOTHING RETURNING key"
                ),
                {"key": cmd.idempotency_key, "command_type": _COMMAND_TYPE},
            )
        ).first()
        return claimed is not None

    async def persist_success(
        self, conn: AsyncConnection, cmd: TransferMoneyCommand
    ) -> ExecutionResult:
        if not await self._try_claim(conn, cmd):
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        transactions = PostgresMoneyTransactionRepository(conn)
        transaction = await transactions.record(
            organization_id=uuid.UUID(cmd.organization_id),
            transaction_type="transfer",
            amount=cmd.amount,
            occurred_date=cmd.occurred_date,
            created_by=uuid.UUID(cmd.created_by),
            from_account_id=uuid.UUID(cmd.from_account_id),
            to_account_id=uuid.UUID(cmd.to_account_id),
            description=cmd.description,
            correlation_id=cmd.correlation_id,
        )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=str(transaction.id),
        )
        await conn.execute(
            sa.text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": cmd.idempotency_key},
        )
        await self._transition(conn, cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_rejection(
        self, conn: AsyncConnection, cmd: TransferMoneyCommand, reasons: list[str]
    ) -> ExecutionResult:
        if not await self._try_claim(conn, cmd):
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        await conn.execute(
            sa.text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": cmd.idempotency_key},
        )
        await self._transition(conn, cmd.idempotency_key, WorkflowPhase.EXECUTION_REJECTED)
        return result

    async def _transition(
        self, conn: AsyncConnection, workflow_instance_id: str, new_phase: WorkflowPhase
    ) -> None:
        try:
            loaded = await get_by_id_on_connection(conn, workflow_instance_id)
        except ValueError:
            return
        if loaded is None:
            return
        new_state = loaded.state.model_copy(update={"phase": new_phase})
        await transition_on_connection(conn, workflow_instance_id, loaded.version, new_state)
