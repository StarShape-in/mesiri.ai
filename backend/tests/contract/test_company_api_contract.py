"""Contract tests for the /company API endpoints.

These verify that the company-wide administration and WhatsApp message logs endpoints
conform to their required API formats, enforce organization tenancy, and perform correct queries.
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
        await conn.execute(sa.text("DELETE FROM inbound_messages"))
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
            INSERT INTO organizations (id, name, deployment_type, db_route, status, timezone, created_at, updated_at)
            VALUES (:id, :name, :deployment_type, :db_route, :status, :timezone, now(), now())
            """),
            {
                "id": org_id,
                "name": "Acme Builders",
                "deployment_type": "local",
                "db_route": "default",
                "status": "active",
                "timezone": "Asia/Kolkata",
            },
        )
    return org_id


@pytest.fixture
async def test_user(test_engine: AsyncEngine, test_org: uuid.UUID):
    """Create a test admin user."""
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
                "email": "admin@acme.com",
                "pwd": "hashed",
                "name": "Acme Admin",
                "role": "ADMIN",
                "status": "active",
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
    return user_id


@pytest.fixture
async def auth_token(test_user: uuid.UUID, test_org: uuid.UUID) -> str:
    """Create a valid JWT token for the admin user."""
    return create_access_token(
        data={
            "sub": str(test_user),
            "org": str(test_org),
            "role": "ADMIN",
        }
    )


# ============================================================================
# CONTRACT TESTS — COMPANY PROFILE & SUMMARY
# ============================================================================


@pytest.mark.integration
async def test_get_company_profile(
    client: AsyncClient,
    clean_db,
    test_org: uuid.UUID,
    auth_token: str,
):
    headers = {"Authorization": f"Bearer {auth_token}"}
    res = await client.get("/company", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(test_org)
    assert data["name"] == "Acme Builders"
    assert data["status"] == "active"
    assert data["timezone"] == "Asia/Kolkata"


@pytest.mark.integration
async def test_patch_company_profile(
    client: AsyncClient,
    clean_db,
    test_org: uuid.UUID,
    auth_token: str,
):
    headers = {"Authorization": f"Bearer {auth_token}"}
    update_data = {
        "name": "Acme Global Builders",
        "email": "contact@acme-global.com",
        "timezone": "Europe/London",
    }
    res = await client.patch("/company", headers=headers, json=update_data)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Acme Global Builders"
    assert data["email"] == "contact@acme-global.com"
    assert data["timezone"] == "Europe/London"


@pytest.mark.integration
async def test_get_company_summary_metrics(
    client: AsyncClient,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    auth_token: str,
):
    headers = {"Authorization": f"Bearer {auth_token}"}
    res = await client.get("/company/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_users"] == 1
    assert data["active_users"] == 1
    assert data["admin_count"] == 1
    assert data["wa_mapped_users"] == 0
    assert data["total_projects"] == 0


# ============================================================================
# CONTRACT TESTS — WHATSAPP MESSAGES LOGS
# ============================================================================


@pytest.mark.integration
async def test_whatsapp_messages_endpoints(
    client: AsyncClient,
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    auth_token: str,
):
    # Insert dummy messages
    msg_id = uuid.uuid4()
    corr_id = "test-correlation-123"
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("""
            INSERT INTO inbound_messages (
                id, correlation_id, sender_wa_id, message_type, raw_payload, 
                normalized_message, body_text, dedup_key, raw_payload_captured,
                processing_status, organization_id, received_at, processed_at,
                assistant_reply
            ) VALUES (
                :id, :correlation_id, :sender_wa_id, :message_type, '{}',
                '{}', :body_text, :dedup_key, true,
                'completed', :org_id, now(), now(), :reply
            )
            """),
            {
                "id": msg_id,
                "correlation_id": corr_id,
                "sender_wa_id": "15555550199",
                "message_type": "text",
                "body_text": "Need concrete delivery details for project",
                "dedup_key": "msg-dedup-1",
                "org_id": test_org,
                "reply": "I am looking up the concrete delivery details.",
            },
        )

    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. Test message list
    res = await client.get("/company/whatsapp/messages", headers=headers)
    assert res.status_code == 200
    list_data = res.json()
    assert list_data["total"] == 2  # 1 Inbound + 1 Outbound (assistant_reply is populated)

    inbound_msg = [m for m in list_data["items"] if m["direction"] == "inbound"][0]
    outbound_msg = [m for m in list_data["items"] if m["direction"] == "outbound"][0]

    assert inbound_msg["body"] == "Need concrete delivery details for project"
    assert outbound_msg["body"] == "I am looking up the concrete delivery details."
    assert inbound_msg["sender_wa_id"] == "15555550199"

    # 2. Test message detail
    res = await client.get(f"/company/whatsapp/messages/{msg_id}", headers=headers)
    assert res.status_code == 200
    detail_data = res.json()
    assert detail_data["id"] == str(msg_id)
    assert detail_data["correlation_id"] == corr_id
    assert detail_data["body_text"] == "Need concrete delivery details for project"
    assert detail_data["assistant_reply"] == "I am looking up the concrete delivery details."

    # 3. Test conversation messages list
    res = await client.get("/company/whatsapp/conversations/15555550199/messages", headers=headers)
    assert res.status_code == 200
    conv_data = res.json()
    assert len(conv_data) == 2  # Inbound and Outbound in the correct chronological flow
