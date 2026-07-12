"""Integration tests for PostgresExpenseCategoryResolver + get_or_create_default:
category_id lookup (REST path, hard rejection on miss), category_text exact
match (WhatsApp path), and the "Uncategorized" default fallback for both an
unmatched AI-guessed category_text and no category at all.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.resolution import PostgresExpenseCategoryResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseCategoryRepository

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
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Category Resolver Org', 'local', "
                "'default', 'active', now(), now())"
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
                "VALUES (:id, :org_id, 'Category Resolver Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'Materials', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
    yield {"org_id": org_id, "user_id": user_id, "project_id": project_id, "category_id": category_id}
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(
            sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id}
        )
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def _command(scenario: dict, **overrides) -> RecordExpenseCommand:
    base = dict(
        idempotency_key=str(uuid.uuid4()),
        organization_id=str(scenario["org_id"]),
        project_id=str(scenario["project_id"]),
        amount=Decimal("100.00"),
        occurred_date=datetime.date.today(),
        created_by=str(scenario["user_id"]),
    )
    base.update(overrides)
    return RecordExpenseCommand(**base)


async def test_category_id_resolves_directly(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        resolver = PostgresExpenseCategoryResolver()
        result = await resolver.resolve(
            conn, _command(scenario, category_id=str(scenario["category_id"]))
        )
    assert result.category_id == scenario["category_id"]
    assert result.reasons == []


async def test_unknown_category_id_is_rejected(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        resolver = PostgresExpenseCategoryResolver()
        result = await resolver.resolve(
            conn, _command(scenario, category_id=str(uuid.uuid4()))
        )
    assert result.category_id is None
    assert result.reasons != []


async def test_matching_category_text_resolves(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        resolver = PostgresExpenseCategoryResolver()
        result = await resolver.resolve(
            conn, _command(scenario, category_text="materials")  # case-insensitive
        )
    assert result.category_id == scenario["category_id"]
    assert result.reasons == []


async def test_unmatched_category_text_falls_back_to_uncategorized_not_rejected(
    engine: AsyncEngine, scenario: dict
):
    """An AI-guessed category that doesn't match any real category must not
    reject the expense -- it degrades to the default bucket instead."""
    async with engine.begin() as conn:
        resolver = PostgresExpenseCategoryResolver()
        result = await resolver.resolve(
            conn, _command(scenario, category_text="something the AI made up")
        )
    assert result.reasons == []
    assert result.category_id is not None
    assert result.category_id != scenario["category_id"]

    async with engine.connect() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        category = await repo.get_by_id(scenario["org_id"], result.category_id)
    assert category is not None
    assert category.name == "Uncategorized"


async def test_no_category_at_all_falls_back_to_uncategorized(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        resolver = PostgresExpenseCategoryResolver()
        result = await resolver.resolve(conn, _command(scenario))
    assert result.reasons == []
    assert result.category_id is not None


async def test_get_or_create_default_is_idempotent(engine: AsyncEngine, scenario: dict):
    """Two concurrent-ish first-uses must land on the same "Uncategorized"
    row, not create duplicates (ON CONFLICT DO NOTHING on org+name)."""
    async with engine.begin() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        first = await repo.get_or_create_default(scenario["org_id"], created_by=scenario["user_id"])
        second = await repo.get_or_create_default(scenario["org_id"], created_by=scenario["user_id"])
    assert first.id == second.id
    assert first.name == "Uncategorized"
