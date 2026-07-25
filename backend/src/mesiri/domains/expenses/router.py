"""Narrow REST API for expenses (M9 scope): RecordExpense + read-back only.

No WhatsApp/Planner, no budgets, no payments/attachments endpoints yet —
those are separate, later work (see application/expenses/commands.py's
docstring on why RecordExpenseCommand is local rather than a shared
contract). RecordExpense is idempotent via a client-supplied `Idempotency-Key`
header, backed by the same `idempotency_keys` table Materials' CQRS path uses
(see application/expenses/repository.py's docstring for how the transaction-
ownership model differs from that path).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.handlers import RecordExpenseHandler
from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.expenses.responses import ExpenseResponse, RecordExpenseResponse
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.expense_execution import (
    PostgresExpenseExecutionRepository,
)
from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository
from mesiri_contracts.application.results.execution_result import ExecutionStatus

router = APIRouter(prefix="/expenses", tags=["expenses"])


class RecordExpenseRequest(BaseModel):
    project_id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    occurred_date: datetime.date
    site_id: uuid.UUID | None = None
    currency: str = "INR"
    description: str | None = None
    occurred_time: datetime.time | None = None
    source: str = "web"
    source_message_id: str | None = None
    correlation_id: str | None = None


def _authorize_write(
    auth_context: AuthorizationContext, project_id: uuid.UUID, site_id: uuid.UUID | None
) -> None:
    if not auth_context.project_scope.grants_all_org_projects:
        if project_id not in auth_context.project_scope.project_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    if site_id is not None:
        site_scope = auth_context.site_scope_for_project(project_id)
        if not site_scope.grants_all_sites and site_id not in site_scope.site_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this site")


@router.post("", response_model=RecordExpenseResponse)
async def record_expense(
    body: RecordExpenseRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Record an expense. Retried requests with the same Idempotency-Key
    return the original outcome rather than creating a second expense."""
    _authorize_write(auth_context, body.project_id, body.site_id)

    cmd = RecordExpenseCommand(
        idempotency_key=idempotency_key,
        organization_id=str(auth_context.organization_id),
        project_id=str(body.project_id),
        site_id=str(body.site_id) if body.site_id else None,
        category_id=str(body.category_id),
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        occurred_date=body.occurred_date,
        occurred_time=body.occurred_time,
        source=body.source,
        source_message_id=body.source_message_id,
        correlation_id=body.correlation_id,
        created_by=str(auth_context.user_id),
    )

    handler = RecordExpenseHandler(PostgresExpenseExecutionRepository())
    result = await handler.handle(conn, cmd)

    if result.status == ExecutionStatus.REJECTED:
        raise HTTPException(status_code=422, detail=result.rejection_reasons)

    status_code = 201 if result.status == ExecutionStatus.SUCCEEDED else 200
    return JSONResponse(
        status_code=status_code,
        content={"id": result.material_row_id, "status": result.status.value},
    )


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    project_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresExpenseRepository(conn)
    items = await repo.list_confirmed(
        auth_context.organization_id,
        project_id=project_id,
        site_id=site_id,
    )
    return [
        ExpenseResponse(
            id=item.id,
            organization_id=item.organization_id,
            project_id=item.project_id,
            site_id=item.site_id,
            category_id=item.category_id,
            amount=item.amount,
            currency=item.currency,
            description=item.description,
            occurred_date=item.occurred_date,
            occurred_time=item.occurred_time,
            workflow_status=item.workflow_status,
            payment_status=item.payment_status,
            source=item.source,
            source_message_id=item.source_message_id,
            correlation_id=item.correlation_id,
            created_by=item.created_by,
        )
        for item in items
    ]


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresExpenseRepository(conn)
    expense = await repo.get_by_id(auth_context.organization_id, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return ExpenseResponse(
        id=expense.id,
        organization_id=expense.organization_id,
        project_id=expense.project_id,
        site_id=expense.site_id,
        category_id=expense.category_id,
        amount=expense.amount,
        currency=expense.currency,
        description=expense.description,
        occurred_date=expense.occurred_date,
        occurred_time=expense.occurred_time,
        workflow_status=expense.workflow_status,
        payment_status=expense.payment_status,
        source=expense.source,
        source_message_id=expense.source_message_id,
        correlation_id=expense.correlation_id,
        created_by=expense.created_by,
    )
