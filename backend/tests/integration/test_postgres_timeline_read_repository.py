"""Integration tests for PostgresTimelineReadRepository."""

from __future__ import annotations

import datetime
import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.timeline import PostgresTimelineReadRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    """Clean test tables before each test."""
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM timeline_entries"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def test_org(test_engine: AsyncEngine):
    """Create a test organization."""
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
    """Create a test user."""
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


@pytest.fixture
async def test_project(test_engine: AsyncEngine, test_org: uuid.UUID):
    """Create a test project."""
    project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": project_id, "org_id": test_org, "name": "Test Project"},
        )
    return project_id


@pytest.fixture
async def test_project_2(test_engine: AsyncEngine, test_org: uuid.UUID):
    """Create a second test project."""
    project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": project_id, "org_id": test_org, "name": "Test Project 2"},
        )
    return project_id


@pytest.fixture
async def test_site(test_engine: AsyncEngine, test_org: uuid.UUID, test_project: uuid.UUID):
    """Create a test site."""
    site_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO sites (id, project_id, organization_id, name, status, created_at, updated_at)
            VALUES (:id, :project_id, :org_id, :name, 'active', now(), now())
            """),
            {
                "id": site_id,
                "project_id": test_project,
                "org_id": test_org,
                "name": "Test Site",
            },
        )
    return site_id


async def _insert_entry(
    engine: AsyncEngine,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
    event_type: str = "MaterialReceived",
    summary: str = "Test entry",
    occurred_at: datetime.datetime = datetime.datetime(2026, 7, 1, 9, 0, tzinfo=datetime.UTC),
) -> uuid.UUID:
    entry_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO timeline_entries (
                id, organization_id, project_id, site_id, event_type, summary, payload,
                occurred_at, correlation_id, source_aggregate_type, source_aggregate_id, created_at
            ) VALUES (
                :id, :org_id, :project_id, :site_id, :event_type, :summary, CAST(:payload AS jsonb),
                :occurred_at, NULL, 'material_receipt', :source_id, now()
            )
            """),
            {
                "id": entry_id,
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "event_type": event_type,
                "summary": summary,
                "payload": json.dumps({}),
                "occurred_at": occurred_at,
                "source_id": uuid.uuid4(),
            },
        )
    return entry_id


async def test_organization_scoping(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Entries are strictly isolated by organization_id."""
    other_org = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
            VALUES (:id, 'Other Org', 'local', 'default', 'active', now(), now())
            """),
            {"id": other_org},
        )

    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None)
    await _insert_entry(test_engine, org_id=other_org, project_id=None, site_id=None)

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(organization_id=test_org)
    assert total == 1


async def test_project_ids_filter(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    test_project_2: uuid.UUID,
    clean_db,
):
    """project_ids=set filters; project_ids=None returns all in scope."""
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None)
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project_2, site_id=None)

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)

        items, total = await repo.list_entries(organization_id=test_org, project_ids={test_project})
        assert total == 1
        assert items[0]["project_id"] == test_project

        items, total = await repo.list_entries(organization_id=test_org, project_ids=None)
        assert total == 2


async def test_site_id_filter(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    test_site: uuid.UUID,
    clean_db,
):
    """site_id filters to only entries on that site."""
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=test_site)
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None)

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(organization_id=test_org, site_id=test_site)
    assert total == 1
    assert items[0]["site_id"] == test_site


async def test_event_type_filter(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """event_type filters to entries of that exact type."""
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialReceived")
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialUsed")

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(organization_id=test_org, event_type="MaterialUsed")
    assert total == 1
    assert items[0]["event_type"] == "MaterialUsed"


async def test_date_range_filter(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """date_from/date_to filter on occurred_at's date component."""
    await _insert_entry(
        test_engine, org_id=test_org, project_id=test_project, site_id=None,
        occurred_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
    )
    await _insert_entry(
        test_engine, org_id=test_org, project_id=test_project, site_id=None,
        occurred_at=datetime.datetime(2026, 7, 5, tzinfo=datetime.UTC),
    )
    await _insert_entry(
        test_engine, org_id=test_org, project_id=test_project, site_id=None,
        occurred_at=datetime.datetime(2026, 7, 10, tzinfo=datetime.UTC),
    )

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(
            organization_id=test_org,
            date_from=datetime.date(2026, 7, 2),
            date_to=datetime.date(2026, 7, 9),
        )
    assert total == 1


async def test_pagination(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """limit/offset paginate; total reflects the full filtered set, not the page."""
    for i in range(5):
        await _insert_entry(
            test_engine, org_id=test_org, project_id=test_project, site_id=None,
            occurred_at=datetime.datetime(2026, 7, 1 + i, tzinfo=datetime.UTC),
        )

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        items, total = await repo.list_entries(organization_id=test_org, limit=2, offset=1)
    assert total == 5
    assert len(items) == 2


async def test_day_summary_aggregation(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Entries on the same day/event_type collapse to one row with the correct count."""
    day1 = datetime.datetime(2026, 7, 1, 9, 0, tzinfo=datetime.UTC)
    day1_later = datetime.datetime(2026, 7, 1, 15, 0, tzinfo=datetime.UTC)
    day2 = datetime.datetime(2026, 7, 2, 9, 0, tzinfo=datetime.UTC)

    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialReceived", occurred_at=day1)
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialReceived", occurred_at=day1_later)
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialUsed", occurred_at=day1)
    await _insert_entry(test_engine, org_id=test_org, project_id=test_project, site_id=None, event_type="MaterialReceived", occurred_at=day2)

    async with test_engine.begin() as conn:
        repo = PostgresTimelineReadRepository(conn)
        summary = await repo.day_summary(organization_id=test_org)

    by_key = {(item["day"], item["event_type"]): item["count"] for item in summary}
    assert by_key[(datetime.date(2026, 7, 1), "MaterialReceived")] == 2
    assert by_key[(datetime.date(2026, 7, 1), "MaterialUsed")] == 1
    assert by_key[(datetime.date(2026, 7, 2), "MaterialReceived")] == 1
