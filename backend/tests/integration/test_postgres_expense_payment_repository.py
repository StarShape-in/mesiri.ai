"""Integration tests for the expense payment / money account domain rules:
unpaid -> partially_paid -> paid, split payments, overpayment rejection,
reversal, account balance calculation, and cross-organization isolation.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expenses import (
    PostgresBudgetRepository,
    PostgresExpensePaymentRepository,
)
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    """One org/user/project/category and two money accounts."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    category_id = uuid.uuid4()
    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Payment Test Org', 'local', 'default', "
                "'active', now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, access_policy, created_at, updated_at) "
                "VALUES (:id, :org_id, :email, 'x', 'Test', 'admin', 'active', "
                "CAST(:policy AS jsonb), now(), now())"
            ),
            {
                "id": user_id,
                "org_id": org_id,
                "email": f"{user_id}@example.com",
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Payment Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'materials', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        for acc_id, name in ((account_a, "Cash A"), (account_b, "Cash B")):
            await conn.execute(
                sa.text(
                    "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                    "currency, opening_balance, opening_balance_date, status, created_by) "
                    "VALUES (:id, :org_id, :name, 'cash', 'INR', 10000.00, current_date, "
                    "'active', :user_id)"
                ),
                {"id": acc_id, "org_id": org_id, "name": name, "user_id": user_id},
            )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "category_id": category_id,
        "account_a": account_a,
        "account_b": account_b,
    }
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def _make_expense(engine: AsyncEngine, scenario: dict, amount: Decimal) -> uuid.UUID:
    expense_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO expenses (id, organization_id, project_id, category_id, amount, "
                "currency, occurred_date, workflow_status, payment_status, source, created_by) "
                "VALUES (:id, :org_id, :project_id, :category_id, :amount, 'INR', current_date, "
                "'confirmed', 'unpaid', 'whatsapp', :user_id)"
            ),
            {
                "id": expense_id,
                "org_id": scenario["org_id"],
                "project_id": scenario["project_id"],
                "category_id": scenario["category_id"],
                "amount": amount,
                "user_id": scenario["user_id"],
            },
        )
    return expense_id


async def test_payment_status_unpaid_to_partial_to_paid(engine: AsyncEngine, scenario: dict):
    expense_id = await _make_expense(engine, scenario, Decimal("1000.00"))
    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        await repo.record_payment(
            organization_id=scenario["org_id"],
            expense_id=expense_id,
            account_id=scenario["account_a"],
            amount=Decimal("400.00"),
            paid_date=datetime.date.today(),
            created_by=scenario["user_id"],
        )
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                sa.text("SELECT payment_status FROM expenses WHERE id = :id"), {"id": expense_id}
            )
        ).scalar_one()
    assert status == "partially_paid"

    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        await repo.record_payment(
            organization_id=scenario["org_id"],
            expense_id=expense_id,
            account_id=scenario["account_b"],
            amount=Decimal("600.00"),
            paid_date=datetime.date.today(),
            created_by=scenario["user_id"],
        )
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                sa.text("SELECT payment_status FROM expenses WHERE id = :id"), {"id": expense_id}
            )
        ).scalar_one()
    assert status == "paid"


async def test_overpayment_is_rejected(engine: AsyncEngine, scenario: dict):
    expense_id = await _make_expense(engine, scenario, Decimal("500.00"))
    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        await repo.record_payment(
            organization_id=scenario["org_id"],
            expense_id=expense_id,
            account_id=scenario["account_a"],
            amount=Decimal("500.00"),
            paid_date=datetime.date.today(),
            created_by=scenario["user_id"],
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        async with engine.begin() as conn:
            repo = PostgresExpensePaymentRepository(conn)
            await repo.record_payment(
                organization_id=scenario["org_id"],
                expense_id=expense_id,
                account_id=scenario["account_b"],
                amount=Decimal("0.01"),
                paid_date=datetime.date.today(),
                created_by=scenario["user_id"],
            )


async def test_payment_reversal_excludes_from_paid_total_and_keeps_history(
    engine: AsyncEngine, scenario: dict
):
    expense_id = await _make_expense(engine, scenario, Decimal("300.00"))
    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        payment = await repo.record_payment(
            organization_id=scenario["org_id"],
            expense_id=expense_id,
            account_id=scenario["account_a"],
            amount=Decimal("300.00"),
            paid_date=datetime.date.today(),
            created_by=scenario["user_id"],
        )

    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        await repo.reverse_payment(scenario["org_id"], payment.id, scenario["user_id"])

    async with engine.connect() as conn:
        payment_row = (
            await conn.execute(
                sa.text("SELECT status FROM expense_payments WHERE id = :id"), {"id": payment.id}
            )
        ).mappings().one()
        expense_status = (
            await conn.execute(
                sa.text("SELECT payment_status FROM expenses WHERE id = :id"), {"id": expense_id}
            )
        ).scalar_one()
        transaction_count = (
            await conn.execute(
                sa.text(
                    "SELECT count(*) FROM money_transactions WHERE source_id = :id "
                    "AND source_type = 'expense_payment'"
                ),
                {"id": payment.id},
            )
        ).scalar_one()

    assert payment_row["status"] == "reversed"
    assert expense_status == "unpaid"
    # Original expense_payment transaction + the reversal transaction: both
    # kept, nothing hard-deleted.
    assert transaction_count == 2


async def test_account_balance_reflects_opening_balance_and_transactions(
    engine: AsyncEngine, scenario: dict
):
    expense_id = await _make_expense(engine, scenario, Decimal("1500.00"))
    async with engine.begin() as conn:
        repo = PostgresExpensePaymentRepository(conn)
        await repo.record_payment(
            organization_id=scenario["org_id"],
            expense_id=expense_id,
            account_id=scenario["account_a"],
            amount=Decimal("1500.00"),
            paid_date=datetime.date.today(),
            created_by=scenario["user_id"],
        )

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        balance = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
    assert balance == Decimal("10000.00") - Decimal("1500.00")


async def test_cross_organization_payment_recording_is_rejected(
    engine: AsyncEngine, scenario: dict
):
    expense_id = await _make_expense(engine, scenario, Decimal("100.00"))
    other_org_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        async with engine.begin() as conn:
            repo = PostgresExpensePaymentRepository(conn)
            await repo.record_payment(
                organization_id=other_org_id,
                expense_id=expense_id,
                account_id=scenario["account_a"],
                amount=Decimal("100.00"),
                paid_date=datetime.date.today(),
                created_by=scenario["user_id"],
            )


async def test_budget_actual_spend_sums_confirmed_expenses_in_project(
    engine: AsyncEngine, scenario: dict
):
    await _make_expense(engine, scenario, Decimal("200.00"))
    await _make_expense(engine, scenario, Decimal("300.00"))

    budget_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO budgets (id, organization_id, project_id, name, amount, currency, "
                "status, created_by) VALUES (:id, :org_id, :project_id, 'Q1 Budget', 5000.00, "
                "'INR', 'active', :user_id)"
            ),
            {
                "id": budget_id,
                "org_id": scenario["org_id"],
                "project_id": scenario["project_id"],
                "user_id": scenario["user_id"],
            },
        )

    async with engine.connect() as conn:
        budgets = PostgresBudgetRepository(conn)
        actual = await budgets.get_actual_spend(scenario["org_id"], budget_id)
    assert actual == Decimal("500.00")
