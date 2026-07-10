"""Integration tests for mesiri.events.consumers.timeline_projector."""

from __future__ import annotations

import asyncio
import datetime
import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.events.consumers.timeline_projector import project_pending_events

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
        await conn.execute(sa.text("DELETE FROM outbox_events"))
        await conn.execute(sa.text("DELETE FROM material_receipts"))
        await conn.execute(sa.text("DELETE FROM material_usage"))
        await conn.execute(sa.text("DELETE FROM workflow_instances"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def test_org(test_engine: AsyncEngine, clean_db):
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


async def _insert_receipt(
    engine: AsyncEngine,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    site_id: uuid.UUID | None,
    user_id: uuid.UUID,
    material_name: str = "Cement",
    quantity: float = 100.0,
    occurred_date: datetime.date = datetime.date(2026, 7, 1),
) -> uuid.UUID:
    row_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO material_receipts (
                id, organization_id, project_id, site_id, material_name, quantity, unit,
                occurred_date, created_by, created_at, updated_at
            ) VALUES (
                :id, :org_id, :project_id, :site_id, :name, :qty, 'bags',
                :date, :user_id, now(), now()
            )
            """),
            {
                "id": row_id,
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "name": material_name,
                "qty": quantity,
                "date": occurred_date,
                "user_id": user_id,
            },
        )
    return row_id


async def _insert_outbox_event(
    engine: AsyncEngine,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict,
    published: bool = False,
    created_at: datetime.datetime | None = None,
) -> uuid.UUID:
    row_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO outbox_events (
                id, aggregate_type, aggregate_id, event_type, payload, correlation_id,
                created_at, published_at
            ) VALUES (
                :id, :aggregate_type, :aggregate_id, :event_type, CAST(:payload AS jsonb),
                NULL, COALESCE(:created_at, now()), :published_at
            )
            """),
            {
                "id": row_id,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": json.dumps(payload),
                "created_at": created_at,
                "published_at": datetime.datetime.now(datetime.UTC) if published else None,
            },
        )
    return row_id


async def test_basic_projection(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    test_site: uuid.UUID,
    clean_db,
):
    """A pending outbox row referencing a real material_receipts row projects correctly."""
    receipt_id = await _insert_receipt(
        test_engine, org_id=test_org, project_id=test_project, site_id=test_site, user_id=test_user
    )
    outbox_id = await _insert_outbox_event(
        test_engine,
        aggregate_type="material_receipt",
        aggregate_id=receipt_id,
        event_type="MaterialReceived",
        payload={
            "material_name": "Cement",
            "quantity": "100.0",
            "unit": "bags",
            "occurred_date": "2026-07-01",
            "occurred_date_source": "reported",
        },
    )

    async with test_engine.begin() as conn:
        count = await project_pending_events(conn)
    assert count == 1

    async with test_engine.begin() as conn:
        entry = (
            await conn.execute(sa.text("SELECT * FROM timeline_entries"))
        ).mappings().first()
        outbox_row = (
            await conn.execute(
                sa.text("SELECT published_at FROM outbox_events WHERE id = :id"),
                {"id": outbox_id},
            )
        ).mappings().first()

    assert entry is not None
    assert entry["organization_id"] == test_org
    assert entry["project_id"] == test_project
    assert entry["site_id"] == test_site
    assert entry["event_type"] == "MaterialReceived"
    assert "Cement" in entry["summary"]
    assert entry["source_aggregate_type"] == "material_receipt"
    assert entry["source_aggregate_id"] == receipt_id
    assert outbox_row["published_at"] is not None


async def test_already_published_rows_are_skipped(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Rows already marked published_at are not re-projected."""
    receipt_id = await _insert_receipt(
        test_engine, org_id=test_org, project_id=test_project, site_id=None, user_id=test_user
    )
    await _insert_outbox_event(
        test_engine,
        aggregate_type="material_receipt",
        aggregate_id=receipt_id,
        event_type="MaterialReceived",
        payload={"material_name": "Cement", "quantity": "1", "unit": "bags"},
        published=True,
    )

    async with test_engine.begin() as conn:
        count = await project_pending_events(conn)
    assert count == 0

    async with test_engine.begin() as conn:
        total = (
            await conn.execute(sa.text("SELECT count(*) FROM timeline_entries"))
        ).scalar_one()
    assert total == 0


async def test_batch_size_and_ordering(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Only batch_size rows are projected per call, oldest created_at first."""
    base_time = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
    outbox_ids = []
    for i in range(5):
        receipt_id = await _insert_receipt(
            test_engine,
            org_id=test_org,
            project_id=test_project,
            site_id=None,
            user_id=test_user,
            material_name=f"Material {i}",
        )
        outbox_id = await _insert_outbox_event(
            test_engine,
            aggregate_type="material_receipt",
            aggregate_id=receipt_id,
            event_type="MaterialReceived",
            payload={"material_name": f"Material {i}", "quantity": "1", "unit": "bags"},
            created_at=base_time + datetime.timedelta(minutes=i),
        )
        outbox_ids.append(outbox_id)

    async with test_engine.begin() as conn:
        count = await project_pending_events(conn, batch_size=3)
    assert count == 3

    async with test_engine.begin() as conn:
        published = (
            await conn.execute(
                sa.text(
                    "SELECT id FROM outbox_events WHERE published_at IS NOT NULL ORDER BY created_at"
                )
            )
        ).scalars().all()
    # The 3 oldest (first inserted) rows are the ones published.
    assert list(published) == outbox_ids[:3]


async def test_missing_source_row_is_marked_published_without_timeline_entry(
    test_engine: AsyncEngine,
    clean_db,
):
    """An outbox row whose aggregate_id doesn't exist doesn't block the batch forever."""
    outbox_id = await _insert_outbox_event(
        test_engine,
        aggregate_type="material_receipt",
        aggregate_id=uuid.uuid4(),  # no matching material_receipts row
        event_type="MaterialReceived",
        payload={"material_name": "Ghost", "quantity": "1", "unit": "bags"},
    )

    async with test_engine.begin() as conn:
        count = await project_pending_events(conn)
    assert count == 0

    async with test_engine.begin() as conn:
        outbox_row = (
            await conn.execute(
                sa.text("SELECT published_at FROM outbox_events WHERE id = :id"),
                {"id": outbox_id},
            )
        ).mappings().first()
        total_entries = (
            await conn.execute(sa.text("SELECT count(*) FROM timeline_entries"))
        ).scalar_one()

    assert outbox_row["published_at"] is not None
    assert total_entries == 0


async def test_unknown_event_type_projects_with_fallback_summary(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """An event_type with no registered summary builder still projects."""
    receipt_id = await _insert_receipt(
        test_engine, org_id=test_org, project_id=test_project, site_id=None, user_id=test_user
    )
    await _insert_outbox_event(
        test_engine,
        aggregate_type="material_receipt",
        aggregate_id=receipt_id,
        event_type="SomeFutureEventType",
        payload={"anything": "goes"},
    )

    async with test_engine.begin() as conn:
        count = await project_pending_events(conn)
    assert count == 1

    async with test_engine.begin() as conn:
        entry = (
            await conn.execute(sa.text("SELECT summary, event_type FROM timeline_entries"))
        ).mappings().first()
    assert entry["event_type"] == "SomeFutureEventType"
    assert entry["summary"]  # non-empty fallback, doesn't raise


async def test_concurrent_projection_does_not_double_project(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Two concurrent drains never project the same outbox row twice (SKIP LOCKED)."""
    for i in range(6):
        receipt_id = await _insert_receipt(
            test_engine,
            org_id=test_org,
            project_id=test_project,
            site_id=None,
            user_id=test_user,
            material_name=f"Concurrent {i}",
        )
        await _insert_outbox_event(
            test_engine,
            aggregate_type="material_receipt",
            aggregate_id=receipt_id,
            event_type="MaterialReceived",
            payload={"material_name": f"Concurrent {i}", "quantity": "1", "unit": "bags"},
        )

    async def _drain() -> int:
        async with test_engine.begin() as conn:
            return await project_pending_events(conn, batch_size=100)

    results = await asyncio.gather(_drain(), _drain())
    assert sum(results) == 6

    async with test_engine.begin() as conn:
        total_entries = (
            await conn.execute(sa.text("SELECT count(*) FROM timeline_entries"))
        ).scalar_one()
        distinct_sources = (
            await conn.execute(
                sa.text("SELECT count(DISTINCT source_aggregate_id) FROM timeline_entries")
            )
        ).scalar_one()

    assert total_entries == 6
    assert distinct_sources == 6
