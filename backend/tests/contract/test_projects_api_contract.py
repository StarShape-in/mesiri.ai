"""Contract tests for GET /projects API endpoint.

These tests lock the canonical external contract currently deployed via the
WhatsApp Assistant projects router (apps/whatsapp-assistant/src/projects/router.py).
The backend implementation must maintain compatibility with this contract so it can
eventually replace the WhatsApp assistant without requiring mobile app changes.

Canonical Contract:
- Endpoint: GET /projects
- Auth: Bearer JWT with 'org' claim
- Response: list of projects with camelCase fields
- Status mapping: on_track→success, at_risk→warning, critical→critical
- Fields: id, name, location, code, client, description, status, statusLabel,
          progress, openIssues, reportingRatio
- Ordering: by name (ascending)
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.domains.identity.auth_service import create_access_token
from mesiri.http.app import create_app
from mesiri.infrastructure.postgres.dependency import get_db_conn


@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    """Clean test tables before each test."""
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM expense_payments"))
        await conn.execute(sa.text("DELETE FROM expense_attachments"))
        await conn.execute(sa.text("DELETE FROM budget_allocations"))
        await conn.execute(sa.text("DELETE FROM budgets"))
        await conn.execute(sa.text("DELETE FROM money_transactions"))
        await conn.execute(sa.text("DELETE FROM expenses"))
        await conn.execute(sa.text("DELETE FROM money_accounts"))
        await conn.execute(sa.text("DELETE FROM expense_categories"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def client(test_engine: AsyncEngine):
    """FastAPI test client."""
    app = create_app()

    async def override_get_db_conn():
        async with test_engine.begin() as conn:
            yield conn

    app.dependency_overrides[get_db_conn] = override_get_db_conn
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client


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
    """Create a test user with default access policy."""
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO users (id, organization_id, email, hashed_password, full_name,
                             role, status, access_policy, created_at, updated_at)
            VALUES (:id, :org_id, :email, :pwd, :name, :role, :status, CAST(:policy AS jsonb),
                    now(), now())
            """),
            {
                "id": user_id,
                "org_id": test_org,
                "email": "test@example.com",
                "pwd": "hashed",
                "name": "Test User",
                "role": "admin",
                "status": "active",
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
    return user_id


@pytest.fixture
async def auth_token(test_user: uuid.UUID, test_org: uuid.UUID) -> str:
    """Create a valid JWT token for the test user."""
    return create_access_token(
        data={
            "sub": str(test_user),
            "org": str(test_org),
            "role": "admin",
        }
    )


# ============================================================================
# CONTRACT TESTS — CANONICAL EXTERNAL BEHAVIOR
# ============================================================================


@pytest.mark.integration
async def test_get_projects_returns_canonical_contract(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify response matches canonical contract with all fields."""
    # Create a project with all fields populated
    project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, code, location, client,
                                description, status, progress, open_issues,
                                created_at, updated_at)
            VALUES (:id, :org_id, :name, :code, :location, :client, :description,
                    :status, :progress, :open_issues, now(), now())
            """),
            {
                "id": project_id,
                "org_id": test_org,
                "name": "Marina Tower",
                "code": "MT-2024",
                "location": "Dubai Marina",
                "client": "Acme Corp",
                "description": "Luxury residential development",
                "status": "at_risk",
                "progress": 65,
                "open_issues": 3,
            },
        )

    response = await client.get(
        "/projects",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1

    project = projects[0]

    # Verify all canonical fields present
    assert "id" in project
    assert "name" in project
    assert "location" in project
    assert "code" in project
    assert "client" in project
    assert "description" in project
    assert "status" in project
    assert "statusLabel" in project
    assert "progress" in project
    assert "openIssues" in project  # camelCase, not snake_case
    assert "reportingRatio" in project

    # Verify field values
    assert project["id"] == str(project_id)
    assert project["name"] == "Marina Tower"
    assert project["code"] == "MT-2024"
    assert project["location"] == "Dubai Marina"
    assert project["client"] == "Acme Corp"
    assert project["description"] == "Luxury residential development"
    assert project["progress"] == 65
    assert project["openIssues"] == 3  # camelCase

    # Verify status mapping: at_risk → warning
    assert project["status"] == "warning"
    assert project["statusLabel"] == "At Risk"

    # reportingRatio not yet implemented
    assert project["reportingRatio"] is None

    # Verify no snake_case fields leak
    assert "open_issues" not in project


@pytest.mark.integration
async def test_status_mapping_on_track_to_success(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify on_track database status maps to success StatusType."""
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, status, created_at, updated_at)
            VALUES (:id, :org_id, :name, :status, now(), now())
            """),
            {
                "id": uuid.uuid4(),
                "org_id": test_org,
                "name": "Test Project",
                "status": "on_track",
            },
        )

    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    project = response.json()[0]
    assert project["status"] == "success"
    assert project["statusLabel"] == "On Track"


@pytest.mark.integration
async def test_status_mapping_critical_to_critical(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify critical database status maps to critical StatusType."""
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, status, created_at, updated_at)
            VALUES (:id, :org_id, :name, :status, now(), now())
            """),
            {
                "id": uuid.uuid4(),
                "org_id": test_org,
                "name": "Test Project",
                "status": "critical",
            },
        )

    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    project = response.json()[0]
    assert project["status"] == "critical"
    assert project["statusLabel"] == "Critical"


@pytest.mark.integration
async def test_projects_ordered_by_name(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify projects are returned ordered by name (ascending)."""
    async with test_engine.begin() as conn:
        for name in ["Zebra Project", "Alpha Project", "Beta Project"]:
            await conn.execute(
                sa.text("""
                INSERT INTO projects (id, organization_id, name, created_at, updated_at)
                VALUES (:id, :org_id, :name, now(), now())
                """),
                {"id": uuid.uuid4(), "org_id": test_org, "name": name},
            )

    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    projects = response.json()
    names = [p["name"] for p in projects]
    assert names == ["Alpha Project", "Beta Project", "Zebra Project"]


@pytest.mark.integration
async def test_empty_projects_returns_empty_list(
    client: AsyncClient,
    clean_db,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify empty result returns empty array, not error."""
    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
async def test_null_optional_fields(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify optional fields can be null."""
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, code, location, client,
                                description, created_at, updated_at)
            VALUES (:id, :org_id, :name, NULL, NULL, NULL, NULL, now(), now())
            """),
            {"id": uuid.uuid4(), "org_id": test_org, "name": "Minimal Project"},
        )

    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    project = response.json()[0]
    assert project["code"] is None
    assert project["location"] is None
    assert project["client"] is None
    assert project["description"] is None
    assert project["reportingRatio"] is None


@pytest.mark.integration
async def test_missing_auth_returns_401(client: AsyncClient):
    """Verify missing authentication returns 401."""
    response = await client.get("/projects")
    assert response.status_code == 401


@pytest.mark.integration
async def test_invalid_token_returns_401(client: AsyncClient):
    """Verify invalid JWT returns 401."""
    response = await client.get("/projects", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401


@pytest.mark.integration
async def test_organization_isolation(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_user: uuid.UUID,
    auth_token: str,
):
    """Verify users only see projects in their organization."""
    # Create another organization with a project
    other_org_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at)
            VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())
            """),
            {
                "id": other_org_id,
                "name": "Other Organization",
                "deployment_type": "local",
                "db_route": "default",
                "status": "active",
            },
        )
        await conn.execute(
            sa.text("""
            INSERT INTO projects (id, organization_id, name, created_at, updated_at)
            VALUES (:id, :org_id, :name, now(), now())
            """),
            {
                "id": uuid.uuid4(),
                "org_id": other_org_id,
                "name": "Other Org Project",
            },
        )

    response = await client.get("/projects", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200
    projects = response.json()
    # Should not see other organization's projects
    assert len(projects) == 0
    assert all(p["name"] != "Other Org Project" for p in projects)
