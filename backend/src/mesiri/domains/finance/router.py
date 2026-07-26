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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.authorization.context import AuthorizationContext
from mesiri.domains.projects.router import get_auth_context
from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.repositories.finance import (
    PostgresMoneyAccountRepository,
    PostgresMoneyTransactionRepository,
)

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
    to_account_id: uuid.UUID | None = None
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

