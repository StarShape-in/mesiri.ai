"""PostgresWorkforceQueryService.create_worker -- real-database integration test.

Mirrors backend/tests/integration/test_timeline_projector.py's fixture
pattern. Nothing in this repository exercised any workforce_query write path
against real Postgres before this file -- list_worker_candidates and
create_worker were both only asserted via SQL-string checks on a fake
connection. This proves the actual INSERT matches the workforce_workers
schema (column names, the created_by NOT NULL foreign key in particular).
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    async def _clean() -> None:
        async with test_engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM workforce_workers"))
            await conn.execute(sa.text("DELETE FROM users"))
            await conn.execute(sa.text("DELETE FROM organizations"))

    await _clean()
    yield
    # Other integration test files' clean_db fixtures delete `users` without
    # knowing about workforce_workers (this file is the first to write there
    # with a `created_by` FK to users.id, which -- unlike organization_id --
    # is NOT ON DELETE CASCADE). In a full-suite run against one shared
    # Postgres (exactly what CI does), a row left behind here breaks whatever
    # other file's clean_db runs next. Clean up after ourselves too, not just
    # before.
    await _clean()


@pytest.fixture
async def test_org(test_engine: AsyncEngine, clean_db):
    org_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
            VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())
            """),
            {
                "id": org_id,
                "name": "Test Organization",
                "deployment_type": "local",
                "db_route": "default",
                "status": "active",
            },
        )
    return org_id


@pytest.fixture
async def test_user(test_engine: AsyncEngine, test_org: uuid.UUID):
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO users (id, organization_id, email, hashed_password, full_name, role, status, created_at, updated_at)
            VALUES (:id, :org_id, :email, 'hash', 'Test User', 'SITE_ENGINEER', 'active', now(), now())
            """),
            {
                "id": user_id,
                "org_id": test_org,
                "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
            },
        )
    return user_id


class _DbAdapter:
    """The slice of PostgresDatabase's interface PostgresWorkforceQueryService
    actually uses -- a `transaction()` async context manager yielding a
    connection with `.execute()`."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def transaction(self):
        return self._engine.begin()


async def test_create_worker_inserts_a_permanent_active_worker(
    test_engine: AsyncEngine, test_org: uuid.UUID, test_user: uuid.UUID
) -> None:
    from runtime.workforce_query import PostgresWorkforceQueryService

    service = PostgresWorkforceQueryService(_DbAdapter(test_engine))

    worker_id = await service.create_worker(
        organization_id=str(test_org),
        name="Ravi Kumar",
        trade="mason",
        daily_wage="850.00",
        created_by=str(test_user),
    )

    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text(
                    "SELECT organization_id, name, trade, worker_type, status, "
                    "default_daily_wage, created_by FROM workforce_workers WHERE id = :id"
                ),
                {"id": uuid.UUID(worker_id)},
            )
        ).mappings().first()

    assert row is not None
    assert row["organization_id"] == test_org
    assert row["name"] == "Ravi Kumar"
    assert row["trade"] == "mason"
    assert row["worker_type"] == "permanent"
    assert row["status"] == "active"
    assert row["default_daily_wage"] == 850
    assert row["created_by"] == test_user


async def test_create_worker_without_a_wage_leaves_it_null(
    test_engine: AsyncEngine, test_org: uuid.UUID, test_user: uuid.UUID
) -> None:
    from runtime.workforce_query import PostgresWorkforceQueryService

    service = PostgresWorkforceQueryService(_DbAdapter(test_engine))

    worker_id = await service.create_worker(
        organization_id=str(test_org),
        name="Arun",
        trade=None,
        daily_wage=None,
        created_by=str(test_user),
    )

    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text("SELECT default_daily_wage, trade FROM workforce_workers WHERE id = :id"),
                {"id": uuid.UUID(worker_id)},
            )
        ).mappings().first()

    assert row["default_daily_wage"] is None
    assert row["trade"] is None


async def test_a_promoted_worker_then_shows_up_as_a_match_candidate(
    test_engine: AsyncEngine, test_org: uuid.UUID, test_user: uuid.UUID
) -> None:
    """The point of promotion: the next attendance report for the same
    person should match them instead of creating a second temp worker."""
    from runtime.workforce_query import PostgresWorkforceQueryService

    service = PostgresWorkforceQueryService(_DbAdapter(test_engine))

    await service.create_worker(
        organization_id=str(test_org),
        name="Ravi Kumar",
        trade="mason",
        daily_wage="850.00",
        created_by=str(test_user),
    )

    candidates = await service.list_worker_candidates(organization_id=str(test_org))

    assert [c["name"] for c in candidates] == ["Ravi Kumar"]
