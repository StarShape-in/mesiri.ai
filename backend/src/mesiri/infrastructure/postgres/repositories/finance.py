from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.domains.finance.entities import MoneyAccount, MoneyTransaction

_money_accounts = sa.Table(
    "money_accounts",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("owner_user_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("account_type", sa.String),
    sa.Column("currency", sa.String),
    sa.Column("opening_balance", sa.Numeric),
    sa.Column("opening_balance_date", sa.Date),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_money_transactions = sa.Table(
    "money_transactions",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("transaction_type", sa.String),
    sa.Column("from_account_id", sa.UUID(as_uuid=True)),
    sa.Column("to_account_id", sa.UUID(as_uuid=True)),
    sa.Column("amount", sa.Numeric),
    sa.Column("source_type", sa.String),
    sa.Column("source_id", sa.UUID(as_uuid=True)),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
    sa.Column("description", sa.String),
    sa.Column("correlation_id", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
)


def _row_to_account(row) -> MoneyAccount:
    return MoneyAccount(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        account_type=row.account_type,
        currency=row.currency,
        opening_balance=row.opening_balance,
        opening_balance_date=row.opening_balance_date,
        status=row.status,
        project_id=row.project_id,
        site_id=row.site_id,
        owner_user_id=row.owner_user_id,
    )


def _row_to_transaction(row) -> MoneyTransaction:
    return MoneyTransaction(
        id=row.id,
        organization_id=row.organization_id,
        transaction_type=row.transaction_type,
        amount=row.amount,
        occurred_date=row.occurred_date,
        occurred_time=row.occurred_time,
        created_by=row.created_by,
        from_account_id=row.from_account_id,
        to_account_id=row.to_account_id,
        source_type=row.source_type,
        source_id=row.source_id,
        description=row.description,
        correlation_id=row.correlation_id,
    )


class PostgresMoneyAccountRepository:
    """PostgreSQL repository for org-scoped money accounts."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def get_by_id(
        self, organization_id: uuid.UUID, account_id: uuid.UUID
    ) -> MoneyAccount | None:
        stmt = sa.select(_money_accounts).where(
            _money_accounts.c.id == account_id,
            _money_accounts.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_account(row) if row else None

    async def list_accounts(
        self,
        organization_id: uuid.UUID,
        account_type: str | None = None,
        status: str | None = None,
    ) -> list[MoneyAccount]:
        where_clauses = [_money_accounts.c.organization_id == organization_id]
        if account_type is not None:
            where_clauses.append(_money_accounts.c.account_type == account_type)
        if status is not None:
            where_clauses.append(_money_accounts.c.status == status)
        stmt = sa.select(_money_accounts).where(*where_clauses).order_by(_money_accounts.c.name)
        res = await self.conn.execute(stmt)
        return [_row_to_account(r) for r in res.mappings().all()]

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        account_type: str,
        currency: str,
        opening_balance: Decimal,
        opening_balance_date: datetime.date,
        created_by: uuid.UUID,
        project_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
        owner_user_id: uuid.UUID | None = None,
    ) -> MoneyAccount:
        new_id = uuid.uuid4()
        await self.conn.execute(
            sa.insert(_money_accounts).values(
                id=new_id,
                organization_id=organization_id,
                project_id=project_id,
                site_id=site_id,
                owner_user_id=owner_user_id,
                name=name,
                account_type=account_type,
                currency=currency,
                opening_balance=opening_balance,
                opening_balance_date=opening_balance_date,
                status="active",
                created_by=created_by,
            )
        )
        return await self.get_by_id(organization_id, new_id)  # type: ignore[return-value]

    async def find_by_name_exact_active(
        self, organization_id: uuid.UUID, name: str
    ) -> MoneyAccount | None:
        """Case-insensitive exact match against active accounts only.
        Mirrors PostgresExpenseCategoryRepository.find_by_name_exact_active."""
        stmt = sa.select(_money_accounts).where(
            _money_accounts.c.organization_id == organization_id,
            _money_accounts.c.status == "active",
            sa.func.lower(_money_accounts.c.name) == name.strip().lower(),
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_account(row) if row else None

    async def rename(
        self, organization_id: uuid.UUID, account_id: uuid.UUID, new_name: str, *, updated_by: uuid.UUID
    ) -> None:
        await self.conn.execute(
            sa.update(_money_accounts)
            .where(
                _money_accounts.c.id == account_id,
                _money_accounts.c.organization_id == organization_id,
            )
            .values(name=new_name, updated_by=updated_by, updated_at=sa.func.now())
        )

    async def deactivate(
        self, organization_id: uuid.UUID, account_id: uuid.UUID, *, updated_by: uuid.UUID
    ) -> None:
        """Status flip only -- never a hard delete. Historical money_transactions
        rows referencing this account stay queryable and keep counting in
        get_balance() (see docs/execution/FINANCE_MODULE_PLAN.md's account
        lifecycle)."""
        await self.conn.execute(
            sa.update(_money_accounts)
            .where(
                _money_accounts.c.id == account_id,
                _money_accounts.c.organization_id == organization_id,
            )
            .values(status="inactive", updated_by=updated_by, updated_at=sa.func.now())
        )

    async def get_balance(self, organization_id: uuid.UUID, account_id: uuid.UUID) -> Decimal:
        """opening_balance + inflows (to_account_id) - outflows (from_account_id).

        Reversed legs of a reversal cancel out naturally since a reversal is
        just another transaction row with the opposite from/to direction —
        there is no mutable balance column to keep in sync.
        """
        account = await self.get_by_id(organization_id, account_id)
        if account is None:
            raise ValueError("money account not found")

        inflow = sa.func.coalesce(
            sa.func.sum(_money_transactions.c.amount), 0
        )
        outflow = sa.func.coalesce(
            sa.func.sum(_money_transactions.c.amount), 0
        )
        inflow_stmt = sa.select(inflow).where(_money_transactions.c.to_account_id == account_id)
        outflow_stmt = sa.select(outflow).where(_money_transactions.c.from_account_id == account_id)
        total_in = (await self.conn.execute(inflow_stmt)).scalar_one()
        total_out = (await self.conn.execute(outflow_stmt)).scalar_one()
        return Decimal(account.opening_balance) + Decimal(total_in) - Decimal(total_out)


class PostgresMoneyTransactionRepository:
    """PostgreSQL repository for the immutable money_transactions ledger.

    Insert-only: confirmed financial history is never updated or deleted.
    Corrections are posted as a new transaction via `reverse`.
    """

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def record(
        self,
        *,
        organization_id: uuid.UUID,
        transaction_type: str,
        amount: Decimal,
        occurred_date: datetime.date,
        created_by: uuid.UUID,
        from_account_id: uuid.UUID | None = None,
        to_account_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: uuid.UUID | None = None,
        description: str | None = None,
        correlation_id: str | None = None,
        occurred_time: datetime.time | None = None,
    ) -> MoneyTransaction:
        new_id = uuid.uuid4()
        await self.conn.execute(
            sa.insert(_money_transactions).values(
                id=new_id,
                organization_id=organization_id,
                transaction_type=transaction_type,
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount=amount,
                source_type=source_type,
                source_id=source_id,
                occurred_date=occurred_date,
                occurred_time=occurred_time,
                description=description,
                correlation_id=correlation_id,
                created_by=created_by,
            )
        )
        res = await self.conn.execute(
            sa.select(_money_transactions).where(_money_transactions.c.id == new_id)
        )
        return _row_to_transaction(res.mappings().one())

    async def get_by_id(
        self, organization_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> MoneyTransaction | None:
        stmt = sa.select(_money_transactions).where(
            _money_transactions.c.id == transaction_id,
            _money_transactions.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_transaction(row) if row else None

    async def reverse(
        self, organization_id: uuid.UUID, transaction_id: uuid.UUID, created_by: uuid.UUID
    ) -> MoneyTransaction:
        original = await self.get_by_id(organization_id, transaction_id)
        if original is None:
            raise ValueError("money transaction not found")
        return await self.record(
            organization_id=organization_id,
            transaction_type="reversal",
            amount=original.amount,
            occurred_date=datetime.date.today(),
            created_by=created_by,
            from_account_id=original.to_account_id,
            to_account_id=original.from_account_id,
            source_type="money_transaction",
            source_id=original.id,
        )
