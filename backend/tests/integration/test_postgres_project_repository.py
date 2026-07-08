"""Integration tests for PostgresProjectRepository.

Tests the repository against a live PostgreSQL database.
Requires docker/CI environment with database.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.projects import PostgresProjectRepository

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
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def test_org(test_engine: AsyncEngine):
    """Create test organization."""
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


async def test_list_all_projects_in_org(test_engine: AsyncEngine, test_org: uuid.UUID, clean_db):
    """Test listing all projects in organization."""
    # Create test projects
    project_ids = []
    async with test_engine.begin() as conn:
        for name in ["Alpha", "Beta", "Gamma"]:
            project_id = uuid.uuid4()
            project_ids.append(project_id)
            await conn.execute(
                sa.text("""
                INSERT INTO projects (id, organization_id, name, status, progress,
                                    open_issues, created_at, updated_at)
                VALUES (:id, :org_id, :name, :status, :progress, :issues, now(), now())
                """),
                {
                    "id": project_id,
                    "org_id": test_org,
                    "name": name,
                    "status": "on_track",
                    "progress": 50,
                    "issues": 0,
                },
            )

    # Query with all_projects scope
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=test_org,
            all_projects=True,
        )

    assert len(projects) == 3
    assert [p.name for p in projects] == ["Alpha", "Beta", "Gamma"]  # Ordered by name


async def test_list_custom_projects_scope(test_engine: AsyncEngine, test_org: uuid.UUID, clean_db):
    """Test listing only explicitly granted projects."""
    # Create three projects
    project_ids = []
    async with test_engine.begin() as conn:
        for name in ["Alpha", "Beta", "Gamma"]:
            project_id = uuid.uuid4()
            project_ids.append(project_id)
            await conn.execute(
                sa.text("""
                INSERT INTO projects (id, organization_id, name, created_at, updated_at)
                VALUES (:id, :org_id, :name, now(), now())
                """),
                {"id": project_id, "org_id": test_org, "name": name},
            )

    # Query with custom scope (only first two projects)
    granted_ids = {project_ids[0], project_ids[1]}
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=test_org,
            all_projects=False,
            project_ids=granted_ids,
        )

    assert len(projects) == 2
    returned_ids = {p.id for p in projects}
    assert returned_ids == granted_ids


async def test_empty_custom_scope_returns_zero_projects(
    test_engine: AsyncEngine,
    test_org: uuid.UUID,
    clean_db,
):
    """Test that empty custom scope returns no projects (safety check)."""
    # Create projects
    async with test_engine.begin() as conn:
        for name in ["Alpha", "Beta"]:
            await conn.execute(
                sa.text("""
                INSERT INTO projects (id, organization_id, name, created_at, updated_at)
                VALUES (:id, :org_id, :name, now(), now())
                """),
                {"id": uuid.uuid4(), "org_id": test_org, "name": name},
            )

    # Query with empty custom scope
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=test_org,
            all_projects=False,
            project_ids=set(),  # Empty set
        )

    # CRITICAL: Empty custom scope must return zero projects
    assert len(projects) == 0


async def test_organization_isolation(test_engine: AsyncEngine, clean_db):
    """Test that projects are isolated by organization."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    # Create two organizations
    async with test_engine.begin() as conn:
        for org_id, org_name in [(org_a, "Org A"), (org_b, "Org B")]:
            await conn.execute(
                sa.text("""
                INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
                VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())
                """),
                {
                    "id": org_id,
                    "name": org_name,
                    "deployment_type": "local",
                    "db_route": "default",
                    "status": "active",
                },
            )

    # Create projects in both orgs
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": org_a, "name": "Org A Project"},
        )
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": org_b, "name": "Org B Project"},
        )

    # Query for org A projects
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=org_a,
            all_projects=True,
        )

    assert len(projects) == 1
    assert projects[0].name == "Org A Project"
    assert projects[0].organization_id == org_a


async def test_custom_scope_respects_organization(test_engine: AsyncEngine, clean_db):
    """Test that custom scope cannot access projects from other organizations."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    # Create two organizations
    async with test_engine.begin() as conn:
        for org_id, org_name in [(org_a, "Org A"), (org_b, "Org B")]:
            await conn.execute(
                sa.text("""
                INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
                VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())
                """),
                {
                    "id": org_id,
                    "name": org_name,
                    "deployment_type": "local",
                    "db_route": "default",
                    "status": "active",
                },
            )

    # Create project in org B
    org_b_project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {"id": org_b_project_id, "org_id": org_b, "name": "Org B Project"},
        )

    # Try to query org A with org B's project ID (should return nothing)
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=org_a,
            all_projects=False,
            project_ids={org_b_project_id},
        )

    # CRITICAL: Cannot access other org's projects even with explicit ID
    assert len(projects) == 0


async def test_projects_ordered_by_name(test_engine: AsyncEngine, test_org: uuid.UUID, clean_db):
    """Test that projects are returned ordered by name."""
    # Create projects in random order
    async with test_engine.begin() as conn:
        for name in ["Zebra", "Alpha", "Gamma", "Beta"]:
            await conn.execute(
                sa.text("""
                INSERT INTO projects (id, organization_id, name, created_at, updated_at)
                VALUES (:id, :org_id, :name, now(), now())
                """),
                {"id": uuid.uuid4(), "org_id": test_org, "name": name},
            )

    # Query projects
    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=test_org,
            all_projects=True,
        )

    # Verify ordered by name
    names = [p.name for p in projects]
    assert names == ["Alpha", "Beta", "Gamma", "Zebra"]


async def test_dto_field_mapping(test_engine: AsyncEngine, test_org: uuid.UUID, clean_db):
    """Test that all project fields are correctly mapped to DTO."""
    project_id = uuid.uuid4()

    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, code, location, client,
                                description, status, progress, open_issues,
                                created_at, updated_at)
            VALUES (:id, :org_id, :name, :code, :location, :client, :description,
                    :status, :progress, :issues, now(), now())
            """),
            {
                "id": project_id,
                "org_id": test_org,
                "name": "Test Project",
                "code": "TEST-001",
                "location": "New York",
                "client": "Acme Corp",
                "description": "A test project",
                "status": "at_risk",
                "progress": 65,
                "issues": 3,
            },
        )

    async with test_engine.begin() as conn:
        repository = PostgresProjectRepository(conn)
        projects = await repository.list_projects_by_scope(
            organization_id=test_org,
            all_projects=True,
        )

    assert len(projects) == 1
    project = projects[0]

    assert project.id == project_id
    assert project.organization_id == test_org
    assert project.name == "Test Project"
    assert project.code == "TEST-001"
    assert project.location == "New York"
    assert project.client == "Acme Corp"
    assert project.description == "A test project"
    assert project.status == "at_risk"
    assert project.progress == 65
    assert project.open_issues == 3
