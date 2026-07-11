"""Contract/integration tests for the dashboard Materials API.

Covers: catalog CRUD + org isolation, valid/invalid Inflow & Outflow writes
(direction/reason enforcement, quantity>0, site-must-belong-to-project,
inaccessible-project rejection), inventory derivation (including negative
stock), and correction/reversal preserving the original movement.

Requires a live Postgres reachable via Settings().postgres.dsn() — run with
`pytest -m integration`. Mirrors the fixture style of
test_projects_api_contract.py.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.domains.identity.auth_service import create_access_token
from mesiri.http.app import create_app
from mesiri.infrastructure.postgres.dependency import get_db_conn

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM material_receipts"))
        await conn.execute(sa.text("DELETE FROM material_usage"))
        await conn.execute(sa.text("DELETE FROM materials_catalog"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def client(test_engine: AsyncEngine):
    app = create_app()

    async def override_get_db_conn():
        async with test_engine.begin() as conn:
            yield conn

    app.dependency_overrides[get_db_conn] = override_get_db_conn
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as test_client:
        yield test_client


@pytest.fixture
async def test_org(test_engine: AsyncEngine, clean_db):
    org_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, :name, 'local', 'default', 'active', now(), now())"
            ),
            {"id": org_id, "name": "Test Org"},
        )
    return org_id


async def _make_user(test_engine, org_id, role: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, access_policy, created_at, updated_at) "
                "VALUES (:id, :org_id, :email, 'hash', 'Test User', :role, 'active', "
                "CAST(:policy AS jsonb), now(), now())"
            ),
            {
                "id": user_id,
                "org_id": org_id,
                "email": f"{uuid.uuid4().hex[:8]}@example.com",
                "role": role,
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
    return user_id


def _token(user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> str:
    return create_access_token(data={"sub": str(user_id), "org": str(org_id), "role": role})


async def _make_project(test_engine, org_id) -> uuid.UUID:
    project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
    return project_id


async def _make_site(test_engine, org_id, project_id) -> uuid.UUID:
    site_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO sites (id, project_id, organization_id, name, status, "
                "created_at, updated_at) VALUES (:id, :project_id, :org_id, 'Test Site', "
                "'active', now(), now())"
            ),
            {"id": site_id, "project_id": project_id, "org_id": org_id},
        )
    return site_id


@pytest.fixture
async def admin_ctx(test_engine, test_org):
    user_id = await _make_user(test_engine, test_org, "admin")
    project_id = await _make_project(test_engine, test_org)
    site_id = await _make_site(test_engine, test_org, project_id)
    token = _token(user_id, test_org, "admin")
    return {"user_id": user_id, "project_id": project_id, "site_id": site_id, "token": token}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_create_material_and_org_isolation(client, test_engine, test_org, admin_ctx):
    resp = await client.post(
        "/materials", json={"name": "Cement", "default_unit": "bags"}, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Cement"

    other_org = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Other Org', 'local', 'default', 'active', now(), now())"
            ),
            {"id": other_org},
        )
    other_user = await _make_user(test_engine, other_org, "admin")
    other_token = _token(other_user, other_org, "admin")

    resp = await client.get("/materials", headers=_auth(other_token))
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_duplicate_material_name_rejected(client, admin_ctx):
    await client.post("/materials", json={"name": "Sand"}, headers=_auth(admin_ctx["token"]))
    resp = await client.post("/materials", json={"name": "Sand"}, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 409


async def test_valid_inflow_then_outflow_derives_inventory(client, admin_ctx):
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_name": "Cement",
        "quantity": "100",
        "unit": "bags",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    out_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_name": "Cement",
        "quantity": "30",
        "unit": "bags",
        "movement_reason": "CONSUMED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/outflows", json=out_body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["current_stock"] == "70.00"
    assert rows[0]["stock_state"] == "AVAILABLE"


async def test_outflow_exceeding_stock_surfaces_negative(client, admin_ctx):
    out_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_name": "Rebar",
        "quantity": "10",
        "unit": "tons",
        "movement_reason": "CONSUMED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/outflows", json=out_body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    rows = resp.json()
    assert rows[0]["stock_state"] == "NEGATIVE_STOCK"
    assert rows[0]["current_stock"] == "-10.00"


@pytest.mark.parametrize(
    "endpoint,reason",
    [("/materials/inflows", "CONSUMED"), ("/materials/outflows", "RECEIVED")],
)
async def test_invalid_direction_reason_combo_rejected(client, admin_ctx, endpoint, reason):
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_name": "Cement",
        "quantity": "10",
        "unit": "bags",
        "movement_reason": reason,
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(endpoint, json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_non_positive_quantity_rejected(client, admin_ctx):
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "material_name": "Cement",
        "quantity": "0",
        "unit": "bags",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_site_not_in_project_rejected(client, test_engine, test_org, admin_ctx):
    other_project = await _make_project(test_engine, test_org)
    foreign_site = await _make_site(test_engine, test_org, other_project)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(foreign_site),
        "material_name": "Cement",
        "quantity": "10",
        "unit": "bags",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_inaccessible_project_rejected(client, test_engine, test_org):
    scoped_user = await _make_user(test_engine, test_org, "site_engineer")
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("UPDATE users SET access_policy = CAST(:p AS jsonb) WHERE id = :id"),
            {"p": '{"mode": "custom_projects", "projects": []}', "id": scoped_user},
        )
    token = _token(scoped_user, test_org, "site_engineer")
    other_project = uuid.uuid4()
    body = {
        "project_id": str(other_project),
        "material_name": "Cement",
        "quantity": "10",
        "unit": "bags",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(token))
    assert resp.status_code == 403


async def test_adjustment_reason_forbidden_for_non_elevated_role(client, test_engine, test_org, admin_ctx):
    site_engineer = await _make_user(test_engine, test_org, "site_engineer")
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("UPDATE users SET access_policy = CAST(:p AS jsonb) WHERE id = :id"),
            {"p": '{"mode": "all_projects", "projects": []}', "id": site_engineer},
        )
    token = _token(site_engineer, test_org, "site_engineer")
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "material_name": "Cement",
        "quantity": "10",
        "unit": "bags",
        "movement_reason": "ADJUSTMENT_IN",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(token))
    assert resp.status_code == 403


async def test_reversal_creates_offsetting_movement_and_preserves_original(client, admin_ctx):
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_name": "Cement",
        "quantity": "100",
        "unit": "bags",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    receipt_id = resp.json()["id"]

    resp = await client.post(
        f"/materials/inflows/{receipt_id}/reverse",
        json={"reason_note": "wrong quantity"},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 201

    original = await client.get(f"/materials/inflows/{receipt_id}", headers=_auth(admin_ctx["token"]))
    assert original.status_code == 200
    assert original.json()["quantity"] == "100.00"
    assert original.json()["movement_reason"] == "RECEIVED"

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.json()[0]["current_stock"] == "0.00"


async def test_ledger_running_balance(client, admin_ctx):
    material_resp = await client.post(
        "/materials", json={"name": "Cement", "default_unit": "bags"}, headers=_auth(admin_ctx["token"])
    )
    material_id = material_resp.json()["id"]

    for qty, endpoint, reason in [
        ("50", "/materials/inflows", "RECEIVED"),
        ("20", "/materials/outflows", "CONSUMED"),
        ("10", "/materials/inflows", "RECEIVED"),
    ]:
        body = {
            "project_id": str(admin_ctx["project_id"]),
            "site_id": str(admin_ctx["site_id"]),
            "material_name": "Cement",
            "quantity": qty,
            "unit": "bags",
            "movement_reason": reason,
            "occurred_date": str(datetime.date.today()),
        }
        await client.post(endpoint, json=body, headers=_auth(admin_ctx["token"]))

    resp = await client.get(
        f"/materials/ledger/{admin_ctx['site_id']}/{material_id}", headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 3
    assert payload["current_balance"] == "40.00"
