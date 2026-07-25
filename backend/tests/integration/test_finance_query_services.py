"""Finance Module Slice 2 read paths against a real Postgres:
MoneyAccountQueryService.find_matching_accounts/get_balances and
PostgresExpenseRepository.list_confirmed's filters.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository
from runtime.money_account_query import MoneyAccountQueryService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db():
    settings = Settings()
    database = PostgresDatabase(settings.postgres)
    await database.connect()
    yield database
    await database.disconnect()


@pytest.fixture
async def scenario(db: PostgresDatabase):
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn())
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    category_diesel = uuid.uuid4()
    category_food = uuid.uuid4()
    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Query Test Org', 'local', 'default', "
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
                "VALUES (:id, :org_id, 'Query Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        for cat_id, name in ((category_diesel, "diesel"), (category_food, "food")):
            await conn.execute(
                sa.text(
                    "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                    "VALUES (:id, :org_id, :name, 'active', :user_id)"
                ),
                {"id": cat_id, "org_id": org_id, "name": name, "user_id": user_id},
            )
        for acc_id, name in ((account_a, "Site Cash"), (account_b, "Company Bank")):
            await conn.execute(
                sa.text(
                    "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                    "currency, opening_balance, opening_balance_date, status, created_by) "
                    "VALUES (:id, :org_id, :name, 'cash', 'INR', 5000.00, current_date, "
                    "'active', :user_id)"
                ),
                {"id": acc_id, "org_id": org_id, "name": name, "user_id": user_id},
            )
        today = datetime.date.today()
        old = today - datetime.timedelta(days=90)
        for amount, cat_id, occurred in (
            (Decimal("700.00"), category_diesel, today),
            (Decimal("300.00"), category_food, today),
            (Decimal("450.00"), category_diesel, old),
        ):
            await conn.execute(
                sa.text(
                    "INSERT INTO expenses (id, organization_id, project_id, category_id, amount, "
                    "currency, occurred_date, workflow_status, payment_status, source, created_by) "
                    "VALUES (:id, :org_id, :project_id, :cat_id, :amount, 'INR', :occurred, "
                    "'confirmed', 'unpaid', 'whatsapp', :user_id)"
                ),
                {
                    "id": uuid.uuid4(),
                    "org_id": org_id,
                    "project_id": project_id,
                    "cat_id": cat_id,
                    "amount": amount,
                    "occurred": occurred,
                    "user_id": user_id,
                },
            )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "account_a": account_a,
        "account_b": account_b,
    }
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
    await engine.dispose()


async def test_find_matching_accounts_with_no_name_returns_all(db: PostgresDatabase, scenario: dict):
    service = MoneyAccountQueryService(db)
    accounts = await service.find_matching_accounts(
        organization_id=str(scenario["org_id"]), created_by=str(scenario["user_id"]), account_name=None
    )
    assert {a.name for a in accounts} == {"Site Cash", "Company Bank"}


async def test_find_matching_accounts_by_name_returns_one(db: PostgresDatabase, scenario: dict):
    service = MoneyAccountQueryService(db)
    accounts = await service.find_matching_accounts(
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        account_name="site cash",
    )
    assert len(accounts) == 1
    assert accounts[0].name == "Site Cash"


async def test_find_matching_accounts_unmatched_name_returns_empty(db: PostgresDatabase, scenario: dict):
    service = MoneyAccountQueryService(db)
    accounts = await service.find_matching_accounts(
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        account_name="Nonexistent Account",
    )
    assert accounts == []


async def test_get_balances_returns_one_entry_per_account(db: PostgresDatabase, scenario: dict):
    service = MoneyAccountQueryService(db)
    accounts = await service.list_accounts(
        organization_id=str(scenario["org_id"]), created_by=str(scenario["user_id"])
    )
    balances = await service.get_balances(organization_id=str(scenario["org_id"]), accounts=accounts)
    assert balances[scenario["account_a"]] == Decimal("5000.00")
    assert balances[scenario["account_b"]] == Decimal("5000.00")


async def test_list_confirmed_filters_by_category(db: PostgresDatabase, scenario: dict):
    async with db.transaction() as conn:
        repo = PostgresExpenseRepository(conn)
        all_expenses = await repo.list_confirmed(scenario["org_id"])
        diesel_only = await repo.list_confirmed(
            scenario["org_id"],
            category_id=(
                await repo.conn.execute(
                    sa.text(
                        "SELECT id FROM expense_categories WHERE organization_id = :org_id AND name = 'diesel'"
                    ),
                    {"org_id": scenario["org_id"]},
                )
            ).scalar_one(),
        )
    assert len(all_expenses) == 3
    assert len(diesel_only) == 2
    assert all(e.amount in (Decimal("700.00"), Decimal("450.00")) for e in diesel_only)


async def test_list_confirmed_filters_by_date_range(db: PostgresDatabase, scenario: dict):
    today = datetime.date.today()
    async with db.transaction() as conn:
        repo = PostgresExpenseRepository(conn)
        today_only = await repo.list_confirmed(scenario["org_id"], start_date=today, end_date=today)
    assert len(today_only) == 2
    assert all(e.occurred_date == today for e in today_only)


async def test_list_confirmed_filters_by_project(db: PostgresDatabase, scenario: dict):
    other_project_id = uuid.uuid4()
    async with db.transaction() as conn:
        repo = PostgresExpenseRepository(conn)
        results = await repo.list_confirmed(scenario["org_id"], project_id=other_project_id)
    assert results == []
