"""PostgreSQL implementation of mesiri.application.expenses.repository.ExpenseExecutionRepository.

Only file permitted to hold SQL for RecordExpense execution (capability-
boundary convention, mirrors material_execution.py). Every method takes an
externally-supplied connection — see application/expenses/repository.py's
docstring for how the REST and WhatsApp/CQRS entry points differ in who
supplies it and who owns the workflow_instances transition.

When `cmd.account_id` is set, `persist_success` also records the payment by
composing `PostgresExpensePaymentRepository.record_payment` (same connection,
same transaction) rather than inlining new ledger SQL here — that repository
already owns the expense_payments + money_transactions write and the
payment_status recompute (see infrastructure/postgres/repositories/expenses.py),
and duplicating it would be worse than the minor capability-boundary bend of
calling out to another repository.

When `cmd.media_object_key` is set (the expense was reported from a
WhatsApp image tapped as "Expense" -- see canonicalization/builder.py and
interactions/image_purpose.py), `persist_success` also writes one
`expense_attachments` row (`attachment_type='receipt'`) via
`PostgresExpenseAttachmentRepository.create`, same connection, same
transaction, same reasoning as the payment write above.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa

from backend.postgres.workflow_instance import get_by_id_on_connection, transition_on_connection
from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.repository import ExpenseExecutionRepository
from mesiri.infrastructure.postgres.repositories.expenses import (
    PostgresExpenseAttachmentRepository,
    PostgresExpensePaymentRepository,
)
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

_COMMAND_TYPE = "record_expense"


def _optional_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value is not None else None


class PostgresExpenseExecutionRepository(ExpenseExecutionRepository):
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

    async def _try_claim(self, conn: AsyncConnection, cmd: RecordExpenseCommand) -> bool:
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
        self, conn: AsyncConnection, cmd: RecordExpenseCommand
    ) -> ExecutionResult:
        if not await self._try_claim(conn, cmd):
            # A concurrent request already claimed this key; by the time we
            # reach here that transaction has committed or rolled back, so
            # the row is visible. This call did not perform the write, so a
            # cached SUCCEEDED is reported as ALREADY_EXECUTED.
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        if cmd.category_id is None:
            raise RuntimeError(
                "persist_success called with unresolved category_id — "
                "the Handler must resolve this before calling persist_success"
            )

        expense_id = uuid.uuid4()
        # 'reimbursable' means the payer covered it personally -- no ledger
        # entry yet (see commands.py docstring). Naming an account starts as
        # 'unpaid' too; record_payment below recomputes it to 'paid' once the
        # payment row lands, same as the REST/manual-payment path already does.
        initial_payment_status = "reimbursable" if cmd.paid_from_own_pocket else "unpaid"
        await conn.execute(
            sa.text(
                "INSERT INTO expenses "
                "(id, organization_id, project_id, site_id, category_id, vendor_id, amount, "
                "currency, description, occurred_date, occurred_time, workflow_status, "
                "payment_status, source, source_message_id, correlation_id, created_by) "
                "VALUES (:id, :organization_id, :project_id, :site_id, :category_id, :vendor_id, "
                ":amount, :currency, :description, :occurred_date, :occurred_time, 'confirmed', "
                ":payment_status, :source, :source_message_id, :correlation_id, :created_by)"
            ),
            {
                "id": expense_id,
                "organization_id": uuid.UUID(cmd.organization_id),
                "project_id": uuid.UUID(cmd.project_id),
                "site_id": _optional_uuid(cmd.site_id),
                "category_id": uuid.UUID(cmd.category_id),
                "vendor_id": _optional_uuid(cmd.vendor_id),
                "amount": cmd.amount,
                "currency": cmd.currency,
                "description": cmd.description,
                "occurred_date": cmd.occurred_date,
                "occurred_time": cmd.occurred_time,
                "payment_status": initial_payment_status,
                "source": cmd.source,
                "source_message_id": cmd.source_message_id,
                "correlation_id": cmd.correlation_id,
                "created_by": uuid.UUID(cmd.created_by),
            },
        )

        if cmd.account_id is not None:
            payments = PostgresExpensePaymentRepository(conn)
            await payments.record_payment(
                organization_id=uuid.UUID(cmd.organization_id),
                expense_id=expense_id,
                account_id=uuid.UUID(cmd.account_id),
                amount=cmd.amount,
                paid_date=cmd.occurred_date,
                created_by=uuid.UUID(cmd.created_by),
            )

        if cmd.media_object_key:
            attachments = PostgresExpenseAttachmentRepository(conn)
            await attachments.create(
                expense_id=expense_id,
                media_object_key=cmd.media_object_key,
                attachment_type="receipt",
                created_by=uuid.UUID(cmd.created_by),
            )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=str(expense_id),
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
        self, conn: AsyncConnection, cmd: RecordExpenseCommand, reasons: list[str]
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
        """Move workflow_instances to `new_phase` on the same connection as the
        domain write. No-op when `workflow_instance_id` doesn't match any row —
        including the REST path, whose client-supplied Idempotency-Key is
        never a workflow_instance_id and isn't even guaranteed to be a UUID."""
        try:
            loaded = await get_by_id_on_connection(conn, workflow_instance_id)
        except ValueError:
            return
        if loaded is None:
            return
        new_state = loaded.state.model_copy(update={"phase": new_phase})
        await transition_on_connection(conn, workflow_instance_id, loaded.version, new_state)
