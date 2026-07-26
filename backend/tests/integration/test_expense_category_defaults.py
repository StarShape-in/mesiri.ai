"""Integration tests for PostgresExpenseCategoryRepository.seed_defaults_if_empty:
a brand-new org gets the construction-generic starter set on first read, an
org that already has categories (even just one custom one) is left
untouched, and re-seeding is idempotent (no duplicate rows)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expenses import (
    PostgresExpenseCategoryRepository,
)

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
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Category Defaults Org', 'local', "
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
    yield {"org_id": org_id, "user_id": user_id}
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id}
        )
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def test_empty_org_gets_the_starter_set(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        seeded = await repo.seed_defaults_if_empty(scenario["org_id"], created_by=scenario["user_id"])

    assert {c.name for c in seeded} == {
        "Materials",
        "Labour",
        "Fuel & Transport",
        "Equipment Rental",
        "Site Utilities",
        "Miscellaneous",
    }
    assert all(c.status == "active" for c in seeded)


async def test_seeding_twice_does_not_duplicate(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        first = await repo.seed_defaults_if_empty(scenario["org_id"], created_by=scenario["user_id"])
        second = await repo.seed_defaults_if_empty(scenario["org_id"], created_by=scenario["user_id"])

    assert len(first) == len(second) == 6
    assert {c.id for c in first} == {c.id for c in second}


async def test_org_with_an_existing_category_is_left_untouched(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        custom = await repo.create(
            scenario["org_id"], "Custom Bucket", created_by=scenario["user_id"]
        )

    async with engine.begin() as conn:
        repo = PostgresExpenseCategoryRepository(conn)
        result = await repo.seed_defaults_if_empty(scenario["org_id"], created_by=scenario["user_id"])

    assert len(result) == 1
    assert result[0].id == custom.id
    assert result[0].name == "Custom Bucket"
