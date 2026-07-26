"""REST API for money accounts — read and create.

Mounted at /finance so:
  GET  /finance/accounts              list org accounts (with computed live balance)
  POST /finance/accounts              create a new account
  GET  /finance/accounts/{account_id} get one account with balance
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_handler import TransferMoneyHandler
from mesiri.application.finance.transfer_resolution import PostgresTransferAccountResolver
from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.finance import (
    PostgresMoneyAccountRepository,
    PostgresMoneyTransactionRepository,
)
from mesiri.infrastructure.postgres.repositories.transfer_execution import (
    PostgresTransferExecutionRepository,
)
from mesiri_contracts.application.results.execution_result import ExecutionStatus

router = APIRouter(prefix="/finance", tags=["finance"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MoneyAccountResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    account_type: str
    currency: str
    opening_balance: Decimal
    current_balance: Decimal
    status: str
    project_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    opening_balance_date: datetime.date | None = None


class MoneyTransactionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    transaction_type: str
    amount: Decimal
    occurred_date: datetime.date
    created_by: uuid.UUID
    from_account_id: uuid.UUID | None = None
    from_account_name: str | None = None
    to_account_id: uuid.UUID | None = None
    to_account_name: str | None = None
    source_type: str | None = None
    source_id: uuid.UUID | None = None
    description: str | None = None
    correlation_id: str | None = None



# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class CreateAccountRequest(BaseModel):
    name: str
    account_type: str
    currency: str = "INR"
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: datetime.date | None = None
    project_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None


class TransferMoneyRequest(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal
    description: str | None = None
    occurred_date: datetime.date | None = None
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/accounts", response_model=list[MoneyAccountResponse])
async def list_accounts(
    account_type: str | None = None,
    status: str | None = None,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List all money accounts for the authenticated organization, with live balance."""
    repo = PostgresMoneyAccountRepository(conn)
    accounts = await repo.list_accounts(
        auth_context.organization_id,
        account_type=account_type,
        status=status,
    )
    result = []
    for acc in accounts:
        try:
            balance = await repo.get_balance(auth_context.organization_id, acc.id)
        except Exception:
            balance = acc.opening_balance
        result.append(
            MoneyAccountResponse(
                id=acc.id,
                organization_id=acc.organization_id,
                name=acc.name,
                account_type=acc.account_type,
                currency=acc.currency,
                opening_balance=acc.opening_balance,
                current_balance=balance,
                status=acc.status,
                project_id=acc.project_id,
                site_id=acc.site_id,
                owner_user_id=acc.owner_user_id,
                opening_balance_date=acc.opening_balance_date,
            )
        )
    return result


@router.get("/accounts/{account_id}", response_model=MoneyAccountResponse)
async def get_account(
    account_id: uuid.UUID,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresMoneyAccountRepository(conn)
    acc = await repo.get_by_id(auth_context.organization_id, account_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        balance = await repo.get_balance(auth_context.organization_id, acc.id)
    except Exception:
        balance = acc.opening_balance
    return MoneyAccountResponse(
        id=acc.id,
        organization_id=acc.organization_id,
        name=acc.name,
        account_type=acc.account_type,
        currency=acc.currency,
        opening_balance=acc.opening_balance,
        current_balance=balance,
        status=acc.status,
        project_id=acc.project_id,
        site_id=acc.site_id,
        owner_user_id=acc.owner_user_id,
        opening_balance_date=acc.opening_balance_date,
    )


@router.post("/accounts", response_model=MoneyAccountResponse, status_code=201)
async def create_account(
    body: CreateAccountRequest,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    repo = PostgresMoneyAccountRepository(conn)
    acc = await repo.create(
        organization_id=auth_context.organization_id,
        name=body.name,
        account_type=body.account_type,
        currency=body.currency,
        opening_balance=body.opening_balance,
        opening_balance_date=body.opening_balance_date or datetime.date.today(),
        created_by=auth_context.user_id,
        project_id=body.project_id,
        site_id=body.site_id,
        owner_user_id=body.owner_user_id,
    )
    return MoneyAccountResponse(
        id=acc.id,
        organization_id=acc.organization_id,
        name=acc.name,
        account_type=acc.account_type,
        currency=acc.currency,
        opening_balance=acc.opening_balance,
        current_balance=acc.opening_balance,
        status=acc.status,
        project_id=acc.project_id,
        site_id=acc.site_id,
        owner_user_id=acc.owner_user_id,
        opening_balance_date=acc.opening_balance_date,
    )


@router.get("/accounts/{account_id}/transactions", response_model=list[MoneyTransactionResponse])
async def list_account_transactions(
    account_id: uuid.UUID,
    limit: int = 50,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List transactions (inbound & outbound ledger) for a given account."""
    tx_repo = PostgresMoneyTransactionRepository(conn)
    txs = await tx_repo.list_by_account(auth_context.organization_id, account_id, limit=limit)
    return [
        MoneyTransactionResponse(
            id=t.id,
            organization_id=t.organization_id,
            transaction_type=t.transaction_type,
            amount=t.amount,
            occurred_date=t.occurred_date,
            created_by=t.created_by,
            from_account_id=t.from_account_id,
            to_account_id=t.to_account_id,
            source_type=t.source_type,
            source_id=t.source_id,
            description=t.description,
            correlation_id=t.correlation_id,
        )
        for t in txs
    ]


@router.get("/petty-cash/vouchers", response_model=list[MoneyTransactionResponse])
async def list_petty_cash_vouchers(
    cash_box_id: uuid.UUID | None = None,
    limit: int = 50,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List petty cash voucher transactions."""
    tx_repo = PostgresMoneyTransactionRepository(conn)
    txs = await tx_repo.list_vouchers(auth_context.organization_id, cash_box_id=cash_box_id, limit=limit)
    return [
        MoneyTransactionResponse(
            id=t.id,
            organization_id=t.organization_id,
            transaction_type=t.transaction_type,
            amount=t.amount,
            occurred_date=t.occurred_date,
            created_by=t.created_by,
            from_account_id=t.from_account_id,
            to_account_id=t.to_account_id,
            source_type=t.source_type,
            source_id=t.source_id,
            description=t.description,
            correlation_id=t.correlation_id,
        )
        for t in txs
    ]


@router.get("/transactions", response_model=list[MoneyTransactionResponse])
async def list_transactions(
    transaction_type: str | None = None,
    account_id: uuid.UUID | None = None,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    limit: int = 100,
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """List company-wide money transactions with optional filters and account names."""
    tx_repo = PostgresMoneyTransactionRepository(conn)
    acc_repo = PostgresMoneyAccountRepository(conn)

    txs = await tx_repo.list_all(
        auth_context.organization_id,
        transaction_type=transaction_type,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    # Batch lookup account names for from_account_id and to_account_id
    acc_ids: set[uuid.UUID] = set()
    for t in txs:
        if t.from_account_id:
            acc_ids.add(t.from_account_id)
        if t.to_account_id:
            acc_ids.add(t.to_account_id)

    acc_names: dict[uuid.UUID, str] = {}
    for aid in acc_ids:
        acc = await acc_repo.get_by_id(auth_context.organization_id, aid)
        if acc:
            acc_names[aid] = acc.name

    return [
        MoneyTransactionResponse(
            id=t.id,
            organization_id=t.organization_id,
            transaction_type=t.transaction_type,
            amount=t.amount,
            occurred_date=t.occurred_date,
            created_by=t.created_by,
            from_account_id=t.from_account_id,
            from_account_name=acc_names.get(t.from_account_id) if t.from_account_id else None,
            to_account_id=t.to_account_id,
            to_account_name=acc_names.get(t.to_account_id) if t.to_account_id else None,
            source_type=t.source_type,
            source_id=t.source_id,
            description=t.description,
            correlation_id=t.correlation_id,
        )
        for t in txs
    ]


@router.post("/transfers", status_code=201)
async def transfer_money(
    body: TransferMoneyRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    auth_context: AuthorizationContext = Depends(get_auth_context),
    conn: AsyncConnection = Depends(get_db_conn),
):
    """Transfer money between two money accounts in the organization."""
    cmd = TransferMoneyCommand(
        idempotency_key=idempotency_key,
        organization_id=str(auth_context.organization_id),
        created_by=str(auth_context.user_id),
        created_by_role=auth_context.role,
        from_account_id=str(body.from_account_id),
        to_account_id=str(body.to_account_id),
        amount=body.amount,
        occurred_date=body.occurred_date or datetime.date.today(),
        description=body.description,
        correlation_id=body.correlation_id,
    )

    handler = TransferMoneyHandler(
        repo=PostgresTransferExecutionRepository(),
        resolver=PostgresTransferAccountResolver(),
    )
    result = await handler.handle(conn, cmd)

    if result.status == ExecutionStatus.REJECTED:
        raise HTTPException(status_code=422, detail=result.rejection_reasons)

    return {"id": result.material_row_id, "status": "succeeded"}


