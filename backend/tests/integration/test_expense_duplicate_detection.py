"""PostgresExpenseRepository.find_potential_duplicate — integration tests
against a real Postgres (Finance Module Slice 8, Linear STA-150).

Covers: vendor match takes priority over category, category-only fallback
when no vendor is given, no match when amount/date/vendor/category don't
line up, and the "neither vendor nor category given" short-circuit that
never even queries (amount+date alone is too weak a signal).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    category_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    today = datetime.date.today()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Duplicate Test Org', 'local', 'default', "
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
                "VALUES (:id, :org_id, 'Duplicate Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'fuel', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO vendors (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'ABC Hardware', 'active', :user_id)"
            ),
            {"id": vendor_id, "org_id": org_id, "user_id": user_id},
        )
        # Existing confirmed expense: 700.00, fuel category, ABC Hardware, today.
        await conn.execute(
            sa.text(
                "INSERT INTO expenses (id, organization_id, project_id, category_id, vendor_id, "
                "amount, currency, occurred_date, workflow_status, payment_status, source, "
                "created_by) VALUES (:id, :org_id, :project_id, :category_id, :vendor_id, "
                "700.00, 'INR', :today, 'confirmed', 'unpaid', 'whatsapp', :user_id)"
            ),
            {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "project_id": project_id,
                "category_id": category_id,
                "vendor_id": vendor_id,
                "today": today,
                "user_id": user_id,
            },
        )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "category_id": category_id,
        "vendor_id": vendor_id,
        "today": today,
    }
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM vendors WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
        await conn.execute(sa.text("DELETE FROM users WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def test_matching_vendor_amount_and_date_is_a_duplicate(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseRepository(conn)
        duplicate = await repo.find_potential_duplicate(
            scenario["org_id"],
            amount=Decimal("700.00"),
            occurred_date=scenario["today"],
            project_id=scenario["project_id"],
            vendor_id=scenario["vendor_id"],
        )
    assert duplicate is not None


async def test_category_fallback_when_no_vendor_given(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseRepository(conn)
        duplicate = await repo.find_potential_duplicate(
            scenario["org_id"],
            amount=Decimal("700.00"),
            occurred_date=scenario["today"],
            category_id=scenario["category_id"],
        )
    assert duplicate is not None


async def test_different_amount_is_not_a_duplicate(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseRepository(conn)
        duplicate = await repo.find_potential_duplicate(
            scenario["org_id"],
            amount=Decimal("999.00"),
            occurred_date=scenario["today"],
            vendor_id=scenario["vendor_id"],
        )
    assert duplicate is None


async def test_different_date_is_not_a_duplicate(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseRepository(conn)
        duplicate = await repo.find_potential_duplicate(
            scenario["org_id"],
            amount=Decimal("700.00"),
            occurred_date=scenario["today"] - datetime.timedelta(days=1),
            vendor_id=scenario["vendor_id"],
        )
    assert duplicate is None


async def test_neither_vendor_nor_category_given_skips_the_query_entirely(
    engine: AsyncEngine, scenario: dict
):
    async with engine.connect() as conn:
        repo = PostgresExpenseRepository(conn)
        duplicate = await repo.find_potential_duplicate(
            scenario["org_id"], amount=Decimal("700.00"), occurred_date=scenario["today"]
        )
    assert duplicate is None
