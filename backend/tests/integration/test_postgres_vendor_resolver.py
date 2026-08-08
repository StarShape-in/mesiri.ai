"""Integration tests for PostgresVendorResolver + PostgresVendorRepository.create:
exact-match resolution, create-on-first-use, no-vendor-mentioned stays null,
and idempotent concurrent-ish first use (mirrors
test_postgres_expense_category_resolver.py, minus the "unresolvable" case --
vendor never rejects and never defaults to a shared bucket)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.vendors.resolution import PostgresVendorResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.vendors import PostgresVendorRepository

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
    vendor_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Vendor Resolver Org', 'local', "
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
                "VALUES (:id, :org_id, 'Vendor Resolver Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO vendors (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'ABC Hardware', 'active', :user_id)"
            ),
            {"id": vendor_id, "org_id": org_id, "user_id": user_id},
        )
    yield {"org_id": org_id, "user_id": user_id, "project_id": project_id, "vendor_id": vendor_id}
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM vendors WHERE organization_id = :id"), {"id": org_id})
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


async def test_matching_vendor_text_resolves(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        resolver = PostgresVendorResolver()
        result = await resolver.resolve(
            conn, _command(scenario, vendor_text="abc hardware")  # case-insensitive
        )
    assert result.vendor_id == scenario["vendor_id"]


async def test_no_vendor_mentioned_stays_null(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        resolver = PostgresVendorResolver()
        result = await resolver.resolve(conn, _command(scenario))
    assert result.vendor_id is None


async def test_unmatched_vendor_text_creates_a_new_vendor(engine: AsyncEngine, scenario: dict):
    """A vendor name that doesn't match any existing vendor gets a brand new
    row -- unlike category, there is no shared default bucket to fall into."""
    async with engine.begin() as conn:
        resolver = PostgresVendorResolver()
        result = await resolver.resolve(conn, _command(scenario, vendor_text="New Supplier Co"))
    assert result.vendor_id is not None
    assert result.vendor_id != scenario["vendor_id"]

    async with engine.connect() as conn:
        repo = PostgresVendorRepository(conn)
        vendor = await repo.get_by_id(scenario["org_id"], result.vendor_id)
    assert vendor is not None
    assert vendor.name == "New Supplier Co"


async def test_create_on_first_use_is_idempotent(engine: AsyncEngine, scenario: dict):
    """Two concurrent-ish first-uses of the same new vendor name must land on
    the same row, not create duplicates (ON CONFLICT DO NOTHING on org+name)."""
    async with engine.begin() as conn:
        repo = PostgresVendorRepository(conn)
        first = await repo.create(scenario["org_id"], "Fresh Supplier", created_by=scenario["user_id"])
        second = await repo.create(scenario["org_id"], "Fresh Supplier", created_by=scenario["user_id"])
    assert first.id == second.id
