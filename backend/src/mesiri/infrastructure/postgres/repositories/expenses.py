from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.domains.expenses.entities import (
    Expense,
    ExpenseAttachment,
    ExpenseCategory,
    ExpensePayment,
)
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyTransactionRepository

_expense_categories = sa.Table(
    "expense_categories",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("code", sa.String),
    sa.Column("parent_category_id", sa.UUID(as_uuid=True)),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_expenses = sa.Table(
    "expenses",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("category_id", sa.UUID(as_uuid=True)),
    sa.Column("expense_number", sa.String),
    sa.Column("amount", sa.Numeric),
    sa.Column("currency", sa.String),
    sa.Column("description", sa.String),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
    sa.Column("workflow_status", sa.String),
    sa.Column("payment_status", sa.String),
    sa.Column("source", sa.String),
    sa.Column("source_message_id", sa.String),
    sa.Column("correlation_id", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_expense_attachments = sa.Table(
    "expense_attachments",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("expense_id", sa.UUID(as_uuid=True)),
    sa.Column("media_object_key", sa.String),
    sa.Column("attachment_type", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
)

_expense_payments = sa.Table(
    "expense_payments",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("expense_id", sa.UUID(as_uuid=True)),
    sa.Column("account_id", sa.UUID(as_uuid=True)),
    sa.Column("amount", sa.Numeric),
    sa.Column("payment_method", sa.String),
    sa.Column("reference_number", sa.String),
    sa.Column("paid_date", sa.Date),
    sa.Column("paid_time", sa.Time),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_budgets = sa.Table(
    "budgets",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("amount", sa.Numeric),
    sa.Column("currency", sa.String),
    sa.Column("start_date", sa.Date),
    sa.Column("end_date", sa.Date),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_budget_allocations = sa.Table(
    "budget_allocations",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("budget_id", sa.UUID(as_uuid=True)),
    sa.Column("category_id", sa.UUID(as_uuid=True)),
    sa.Column("amount", sa.Numeric),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)


def _row_to_category(row) -> ExpenseCategory:
    return ExpenseCategory(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        status=row.status,
        code=row.code,
        parent_category_id=row.parent_category_id,
    )


def _row_to_expense(row) -> Expense:
    return Expense(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        category_id=row.category_id,
        amount=row.amount,
        currency=row.currency,
        occurred_date=row.occurred_date,
        workflow_status=row.workflow_status,
        payment_status=row.payment_status,
        source=row.source,
        created_by=row.created_by,
        site_id=row.site_id,
        expense_number=row.expense_number,
        description=row.description,
        occurred_time=row.occurred_time,
        source_message_id=row.source_message_id,
        correlation_id=row.correlation_id,
    )


def _row_to_payment(row) -> ExpensePayment:
    return ExpensePayment(
        id=row.id,
        organization_id=row.organization_id,
        expense_id=row.expense_id,
        account_id=row.account_id,
        amount=row.amount,
        paid_date=row.paid_date,
        status=row.status,
        created_by=row.created_by,
        payment_method=row.payment_method,
        reference_number=row.reference_number,
        paid_time=row.paid_time,
    )


class PostgresExpenseCategoryRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_active(self, organization_id: uuid.UUID) -> list[ExpenseCategory]:
        stmt = (
            sa.select(_expense_categories)
            .where(
                _expense_categories.c.organization_id == organization_id,
                _expense_categories.c.status == "active",
            )
            .order_by(_expense_categories.c.name)
        )
        res = await self.conn.execute(stmt)
        return [_row_to_category(r) for r in res.mappings().all()]

    async def get_by_id(
        self, organization_id: uuid.UUID, category_id: uuid.UUID
    ) -> ExpenseCategory | None:
        stmt = sa.select(_expense_categories).where(
            _expense_categories.c.id == category_id,
            _expense_categories.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_category(row) if row else None

    async def find_by_name_exact_active(
        self, organization_id: uuid.UUID, name: str
    ) -> ExpenseCategory | None:
        """Case-insensitive exact match against active categories only."""
        stmt = sa.select(_expense_categories).where(
            _expense_categories.c.organization_id == organization_id,
            _expense_categories.c.status == "active",
            sa.func.lower(_expense_categories.c.name) == name.strip().lower(),
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_category(row) if row else None

    async def get_or_create_default(
        self, organization_id: uuid.UUID, *, created_by: uuid.UUID
    ) -> ExpenseCategory:
        """The org-scoped "Uncategorized" bucket, created on first use.

        Mirrors migration 0310's `units_of_measure` "unspecified" fallback:
        category is documented as optional on the extraction side, so an
        expense with no category shouldn't be rejected outright — it lands
        here instead. ON CONFLICT DO NOTHING on the (organization_id, name)
        unique constraint makes concurrent first-use races safe.
        """
        existing = await self.find_by_name_exact_active(organization_id, "Uncategorized")
        if existing is not None:
            return existing

        await self.conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :organization_id, 'Uncategorized', 'active', :created_by) "
                "ON CONFLICT (organization_id, name) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "organization_id": organization_id, "created_by": created_by},
        )
        category = await self.find_by_name_exact_active(organization_id, "Uncategorized")
        assert category is not None
        return category


class PostgresExpenseRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def get_by_id(self, organization_id: uuid.UUID, expense_id: uuid.UUID) -> Expense | None:
        stmt = sa.select(_expenses).where(
            _expenses.c.id == expense_id,
            _expenses.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_expense(row) if row else None

    async def list_confirmed(
        self,
        organization_id: uuid.UUID,
        *,
        project_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        category_id: uuid.UUID | None = None,
    ) -> list[Expense]:
        """Confirmed (non-voided, non-draft) expenses matching the given
        filters -- read path for Finance Module Slice 2's expense query
        workflow. All filters are optional and additive (AND'd together)."""
        where_clauses = [
            _expenses.c.organization_id == organization_id,
            _expenses.c.workflow_status == "confirmed",
        ]
        if project_id is not None:
            where_clauses.append(_expenses.c.project_id == project_id)
        if site_id is not None:
            where_clauses.append(_expenses.c.site_id == site_id)
        if start_date is not None:
            where_clauses.append(_expenses.c.occurred_date >= start_date)
        if end_date is not None:
            where_clauses.append(_expenses.c.occurred_date <= end_date)
        if category_id is not None:
            where_clauses.append(_expenses.c.category_id == category_id)

        stmt = (
            sa.select(_expenses)
            .where(*where_clauses)
            .order_by(_expenses.c.occurred_date.desc())
        )
        res = await self.conn.execute(stmt)
        return [_row_to_expense(r) for r in res.mappings().all()]


class PostgresExpenseAttachmentRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_for_expense(
        self, organization_id: uuid.UUID, expense_id: uuid.UUID
    ) -> list[ExpenseAttachment]:
        stmt = (
            sa.select(_expense_attachments)
            .select_from(_expense_attachments.join(_expenses, _expenses.c.id == _expense_attachments.c.expense_id))
            .where(
                _expense_attachments.c.expense_id == expense_id,
                _expenses.c.organization_id == organization_id,
            )
        )
        res = await self.conn.execute(stmt)
        return [
            ExpenseAttachment(
                id=r.id,
                expense_id=r.expense_id,
                media_object_key=r.media_object_key,
                attachment_type=r.attachment_type,
                created_by=r.created_by,
            )
            for r in res.mappings().all()
        ]


class PostgresExpensePaymentRepository:
    """Applies the confirmed-payment domain rules: overpayment rejection,
    atomic payment + money_transaction creation, and payment_status recompute.
    """

    def __init__(self, conn: AsyncConnection):
        self.conn = conn
        self._transactions = PostgresMoneyTransactionRepository(conn)

    async def list_for_expense(
        self, organization_id: uuid.UUID, expense_id: uuid.UUID
    ) -> list[ExpensePayment]:
        stmt = sa.select(_expense_payments).where(
            _expense_payments.c.expense_id == expense_id,
            _expense_payments.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        return [_row_to_payment(r) for r in res.mappings().all()]

    async def _confirmed_paid_total(self, expense_id: uuid.UUID) -> Decimal:
        stmt = sa.select(sa.func.coalesce(sa.func.sum(_expense_payments.c.amount), 0)).where(
            _expense_payments.c.expense_id == expense_id,
            _expense_payments.c.status == "confirmed",
        )
        return Decimal((await self.conn.execute(stmt)).scalar_one())

    async def _recompute_payment_status(self, organization_id: uuid.UUID, expense_id: uuid.UUID) -> None:
        expense_row = (
            await self.conn.execute(
                sa.select(_expenses.c.amount).where(
                    _expenses.c.id == expense_id, _expenses.c.organization_id == organization_id
                )
            )
        ).mappings().one()
        paid_total = await self._confirmed_paid_total(expense_id)
        if paid_total <= 0:
            status = "unpaid"
        elif paid_total < Decimal(expense_row["amount"]):
            status = "partially_paid"
        else:
            status = "paid"
        await self.conn.execute(
            sa.update(_expenses)
            .where(_expenses.c.id == expense_id, _expenses.c.organization_id == organization_id)
            .values(payment_status=status)
        )

    async def record_payment(
        self,
        *,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        account_id: uuid.UUID,
        amount: Decimal,
        paid_date: datetime.date,
        created_by: uuid.UUID,
        payment_method: str | None = None,
        reference_number: str | None = None,
    ) -> ExpensePayment:
        expense_row = (
            await self.conn.execute(
                sa.select(_expenses.c.amount).where(
                    _expenses.c.id == expense_id, _expenses.c.organization_id == organization_id
                )
            )
        ).mappings().first()
        if expense_row is None:
            raise ValueError("expense not found")

        already_paid = await self._confirmed_paid_total(expense_id)
        if already_paid + amount > Decimal(expense_row["amount"]):
            raise ValueError("confirmed payment total cannot exceed expense amount")

        payment_id = uuid.uuid4()
        await self.conn.execute(
            sa.insert(_expense_payments).values(
                id=payment_id,
                organization_id=organization_id,
                expense_id=expense_id,
                account_id=account_id,
                amount=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                paid_date=paid_date,
                status="confirmed",
                created_by=created_by,
            )
        )
        await self._transactions.record(
            organization_id=organization_id,
            transaction_type="expense_payment",
            amount=amount,
            occurred_date=paid_date,
            created_by=created_by,
            from_account_id=account_id,
            source_type="expense_payment",
            source_id=payment_id,
        )
        await self._recompute_payment_status(organization_id, expense_id)

        res = await self.conn.execute(
            sa.select(_expense_payments).where(_expense_payments.c.id == payment_id)
        )
        return _row_to_payment(res.mappings().one())

    async def reverse_payment(
        self, organization_id: uuid.UUID, payment_id: uuid.UUID, created_by: uuid.UUID
    ) -> ExpensePayment:
        payment_row = (
            await self.conn.execute(
                sa.select(_expense_payments).where(
                    _expense_payments.c.id == payment_id,
                    _expense_payments.c.organization_id == organization_id,
                )
            )
        ).mappings().first()
        if payment_row is None:
            raise ValueError("expense payment not found")
        if payment_row["status"] != "confirmed":
            raise ValueError("only confirmed payments can be reversed")

        await self.conn.execute(
            sa.update(_expense_payments)
            .where(_expense_payments.c.id == payment_id)
            .values(status="reversed", updated_by=created_by)
        )
        await self._transactions.record(
            organization_id=organization_id,
            transaction_type="reversal",
            amount=payment_row["amount"],
            occurred_date=datetime.date.today(),
            created_by=created_by,
            to_account_id=payment_row["account_id"],
            source_type="expense_payment",
            source_id=payment_id,
        )
        await self._recompute_payment_status(organization_id, payment_row["expense_id"])

        res = await self.conn.execute(
            sa.select(_expense_payments).where(_expense_payments.c.id == payment_id)
        )
        return _row_to_payment(res.mappings().one())


class PostgresBudgetRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def get_actual_spend(self, organization_id: uuid.UUID, budget_id: uuid.UUID) -> Decimal:
        """Sum of confirmed, non-voided expenses in the budget's project,
        restricted to allocated categories when the budget has allocations."""
        budget_row = (
            await self.conn.execute(
                sa.select(_budgets.c.project_id).where(
                    _budgets.c.id == budget_id, _budgets.c.organization_id == organization_id
                )
            )
        ).mappings().first()
        if budget_row is None:
            raise ValueError("budget not found")

        allocation_categories = (
            await self.conn.execute(
                sa.select(_budget_allocations.c.category_id).where(
                    _budget_allocations.c.budget_id == budget_id,
                    _budget_allocations.c.category_id.is_not(None),
                )
            )
        ).scalars().all()

        where_clauses = [
            _expenses.c.organization_id == organization_id,
            _expenses.c.project_id == budget_row["project_id"],
            _expenses.c.workflow_status == "confirmed",
        ]
        if allocation_categories:
            where_clauses.append(_expenses.c.category_id.in_(allocation_categories))

        stmt = sa.select(sa.func.coalesce(sa.func.sum(_expenses.c.amount), 0)).where(*where_clauses)
        return Decimal((await self.conn.execute(stmt)).scalar_one())
