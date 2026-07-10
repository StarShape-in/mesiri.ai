"""Integration tests for PostgresMaterialReadRepository."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.materials import PostgresMaterialReadRepository

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


async def test_list_receipts_filters_and_pagination(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    test_site: uuid.UUID,
    clean_db,
):
    """Test PostgresMaterialReadRepository.list_receipts with filters and pagination."""
    async with test_engine.begin() as conn:
        # Seed 3 material receipts
        for i, name in enumerate(["Cement", "Steel", "Sand"]):
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
                    "id": uuid.uuid4(),
                    "org_id": test_org,
                    "project_id": test_project,
                    "site_id": test_site if i < 2 else None,
                    "name": name,
                    "qty": 100 + i * 10,
                    "date": datetime.date(2026, 7, 1 + i),
                    "user_id": test_user,
                },
            )

    async with test_engine.begin() as conn:
        repo = PostgresMaterialReadRepository(conn)

        # 1. Test basic list for the organization
        items, total = await repo.list_receipts(organization_id=test_org)
        assert total == 3
        assert len(items) == 3

        # 2. Test site_id filtering
        items, total = await repo.list_receipts(organization_id=test_org, site_id=test_site)
        assert total == 2
        assert {item["material_name"] for item in items} == {"Cement", "Steel"}

        # 3. Test material name filtering (ILIKE)
        items, total = await repo.list_receipts(organization_id=test_org, material_name="ce")
        assert total == 1
        assert items[0]["material_name"] == "Cement"

        # 4. Test date range filtering
        items, total = await repo.list_receipts(
            organization_id=test_org,
            date_from=datetime.date(2026, 7, 2),
            date_to=datetime.date(2026, 7, 3),
        )
        assert total == 2
        assert {item["material_name"] for item in items} == {"Steel", "Sand"}

        # 5. Test pagination (limit/offset)
        items, total = await repo.list_receipts(organization_id=test_org, limit=1, offset=1)
        assert total == 3
        assert len(items) == 1


async def test_list_usage_filters_and_pagination(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Test PostgresMaterialReadRepository.list_usage with filters and pagination."""
    async with test_engine.begin() as conn:
        # Seed 2 material usages
        for i, name in enumerate(["Cement", "Steel"]):
            await conn.execute(
                sa.text("""
                INSERT INTO material_usage (
                    id, organization_id, project_id, material_name, quantity, unit,
                    occurred_date, created_by, created_at, updated_at
                ) VALUES (
                    :id, :org_id, :project_id, :name, :qty, 'bags',
                    :date, :user_id, now(), now()
                )
                """),
                {
                    "id": uuid.uuid4(),
                    "org_id": test_org,
                    "project_id": test_project,
                    "name": name,
                    "qty": 50 + i * 5,
                    "date": datetime.date(2026, 7, 10 + i),
                    "user_id": test_user,
                },
            )

    async with test_engine.begin() as conn:
        repo = PostgresMaterialReadRepository(conn)

        items, total = await repo.list_usage(organization_id=test_org)
        assert total == 2
        assert len(items) == 2


async def test_organization_isolation(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    clean_db,
):
    """Test that material reads are strictly isolated by organization."""
    other_org = uuid.uuid4()
    async with test_engine.begin() as conn:
        # Create other org
        await conn.execute(
            sa.text("""
            INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
            VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())
            """),
            {
                "id": other_org,
                "name": "Other Organization",
                "deployment_type": "local",
                "db_route": "default",
                "status": "active",
            },
        )
        # Create other user
        other_user = uuid.uuid4()
        await conn.execute(
            sa.text("""
            INSERT INTO users (id, organization_id, email, hashed_password, full_name, role, status, created_at, updated_at)
            VALUES (:id, :org_id, :email, 'hash', 'Other User', 'SITE_ENGINEER', 'active', now(), now())
            """),
            {
                "id": other_user,
                "org_id": other_org,
                "email": "other@example.com",
            },
        )
        # Create other project
        other_project = uuid.uuid4()
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": other_project, "org_id": other_org, "name": "Other Project"},
        )

        # Seed receipt in test_org
        await conn.execute(
            sa.text("""
            INSERT INTO material_receipts (
                id, organization_id, project_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, 'Cement', 100, 'bags', '2026-07-01', :user_id, now(), now())
            """),
            {
                "id": uuid.uuid4(),
                "org_id": test_org,
                "project_id": test_project,
                "user_id": test_user,
            },
        )

        # Seed receipt in other_org
        await conn.execute(
            sa.text("""
            INSERT INTO material_receipts (
                id, organization_id, project_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, 'Steel', 200, 'tons', '2026-07-01', :user_id, now(), now())
            """),
            {
                "id": uuid.uuid4(),
                "org_id": other_org,
                "project_id": other_project,
                "user_id": other_user,
            },
        )

    async with test_engine.begin() as conn:
        repo = PostgresMaterialReadRepository(conn)

        # Test org should only see Cement
        items, total = await repo.list_receipts(organization_id=test_org)
        assert total == 1
        assert items[0]["material_name"] == "Cement"

        # Other org should only see Steel
        items, total = await repo.list_receipts(organization_id=other_org)
        assert total == 1
        assert items[0]["material_name"] == "Steel"


async def test_stock_levels_arithmetic_and_joins(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    test_site: uuid.UUID,
    clean_db,
):
    """Test stock level aggregation with FULL OUTER JOIN and nullable site_id."""
    async with test_engine.begin() as conn:
        # Material 1: Cement (has both receipts and usage on test_site)
        # Rec: 100 bags, Used: 40 bags -> Stock: 60 bags
        await conn.execute(
            sa.text("""
            INSERT INTO material_receipts (
                id, organization_id, project_id, site_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, :site_id, 'Cement', 100.0, 'bags', '2026-07-01', :user_id, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": test_org, "project_id": test_project, "site_id": test_site, "user_id": test_user},
        )
        await conn.execute(
            sa.text("""
            INSERT INTO material_usage (
                id, organization_id, project_id, site_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, :site_id, 'Cement', 40.0, 'bags', '2026-07-02', :user_id, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": test_org, "project_id": test_project, "site_id": test_site, "user_id": test_user},
        )

        # Material 2: Steel (receipts only, site_id is NULL)
        # Rec: 10 tons -> Stock: 10 tons
        await conn.execute(
            sa.text("""
            INSERT INTO material_receipts (
                id, organization_id, project_id, site_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, NULL, 'Steel', 10.0, 'tons', '2026-07-01', :user_id, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": test_org, "project_id": test_project, "user_id": test_user},
        )

        # Material 3: Sand (usage only, site_id is NULL)
        # Used: 50.0 cubic meters -> Stock: -50.0
        await conn.execute(
            sa.text("""
            INSERT INTO material_usage (
                id, organization_id, project_id, site_id, material_name, quantity, unit, occurred_date, created_by, created_at, updated_at
            ) VALUES (:id, :org_id, :project_id, NULL, 'Sand', 50.0, 'cum', '2026-07-01', :user_id, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": test_org, "project_id": test_project, "user_id": test_user},
        )

    async with test_engine.begin() as conn:
        repo = PostgresMaterialReadRepository(conn)

        # Query stock levels
        levels = await repo.get_stock_levels(organization_id=test_org)

        # We should have 3 materials in inventory: Cement, Sand, Steel
        assert len(levels) == 3

        # Map to dict by material name
        stock_by_name = {item["material_name"]: item for item in levels}

        # Verify Cement
        cement = stock_by_name["Cement"]
        assert cement["site_id"] == test_site
        assert Decimal(cement["total_received"]) == Decimal("100.00")
        assert Decimal(cement["total_used"]) == Decimal("40.00")
        assert Decimal(cement["current_stock"]) == Decimal("60.00")

        # Verify Steel
        steel = stock_by_name["Steel"]
        assert steel["site_id"] is None
        assert Decimal(steel["total_received"]) == Decimal("10.00")
        assert Decimal(steel["total_used"]) == Decimal("0.00")
        assert Decimal(steel["current_stock"]) == Decimal("10.00")

        # Verify Sand
        sand = stock_by_name["Sand"]
        assert sand["site_id"] is None
        assert Decimal(sand["total_received"]) == Decimal("0.00")
        assert Decimal(sand["total_used"]) == Decimal("50.00")
        assert Decimal(sand["current_stock"]) == Decimal("-50.00")
