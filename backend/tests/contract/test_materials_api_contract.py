"""Contract/integration tests for the dashboard Materials API.

Covers: catalog CRUD + org isolation, Stock Unit enforcement, valid/invalid
Inflow & Outflow writes (direction/reason enforcement, quantity>0,
site-must-belong-to-project, inaccessible-project rejection), inventory
derivation from the material_movements ledger (including negative stock),
and correction/reversal preserving the original movement.

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
        await conn.execute(sa.text("DELETE FROM material_movements"))
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


async def _bags_unit_id(client, token: str) -> str:
    resp = await client.get("/materials/units-of-measure", headers=_auth(token))
    assert resp.status_code == 200
    units = {u["code"]: u["id"] for u in resp.json()["items"]}
    return units["bags"]


async def _tons_unit_id(client, token: str) -> str:
    resp = await client.get("/materials/units-of-measure", headers=_auth(token))
    assert resp.status_code == 200
    units = {u["code"]: u["id"] for u in resp.json()["items"]}
    return units["tons"]


async def _make_material(client, token: str, name: str, unit_id: str) -> str:
    resp = await client.post(
        "/materials",
        json={"name": name, "default_unit_id": unit_id},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_material_and_org_isolation(client, test_engine, test_org, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    resp = await client.post(
        "/materials",
        json={"name": "Cement", "default_unit_id": bags_id},
        headers=_auth(admin_ctx["token"]),
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
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    await client.post(
        "/materials", json={"name": "Sand", "default_unit_id": bags_id}, headers=_auth(admin_ctx["token"])
    )
    resp = await client.post(
        "/materials", json={"name": "Sand", "default_unit_id": bags_id}, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 409


async def test_create_material_with_unknown_unit_rejected(client, admin_ctx):
    resp = await client.post(
        "/materials",
        json={"name": "Gravel", "default_unit_id": str(uuid.uuid4())},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 422


async def test_delete_unused_material_removes_catalog_entry(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Delete Me", bags_id)

    resp = await client.delete(f"/materials/{material_id}", headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 204

    resp = await client.get("/materials", headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 200
    assert all(item["id"] != material_id for item in resp.json()["items"])


async def test_delete_material_with_movements_rejected(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Used Cement", bags_id)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "100",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    resp = await client.delete(f"/materials/{material_id}", headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 409
    assert "Deactivate it instead" in resp.json()["detail"]

    resp = await client.get("/materials", headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 200
    assert any(item["id"] == material_id for item in resp.json()["items"])


async def test_valid_inflow_then_outflow_derives_inventory(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)

    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "100",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    out_body = {**body, "quantity": "30", "movement_reason": "CONSUMED"}
    resp = await client.post(
        "/materials/outflows", json=out_body, headers=_auth(admin_ctx["token"])
    )
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


async def test_outflow_with_unit_mismatched_to_stock_unit_rejected(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    tons_id = await _tons_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Rebar", tons_id)

    out_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,  # Rebar's Stock Unit is tons, not bags
        "quantity": "10",
        "movement_reason": "CONSUMED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(
        "/materials/outflows", json=out_body, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 422


async def test_outflow_exceeding_stock_surfaces_negative(client, admin_ctx):
    tons_id = await _tons_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Rebar", tons_id)

    out_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": tons_id,
        "quantity": "10",
        "movement_reason": "CONSUMED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(
        "/materials/outflows", json=out_body, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 201

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    rows = resp.json()
    assert rows[0]["stock_state"] == "NEGATIVE_STOCK"
    assert rows[0]["current_stock"] == "-10.00"


async def test_unknown_material_id_rejected(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": str(uuid.uuid4()),
        "unit_id": bags_id,
        "quantity": "10",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "endpoint,reason",
    [("/materials/inflows", "CONSUMED"), ("/materials/outflows", "RECEIVED")],
)
async def test_invalid_direction_reason_combo_rejected(client, admin_ctx, endpoint, reason):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "movement_reason": reason,
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(endpoint, json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_non_positive_quantity_rejected(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "0",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_site_not_in_project_rejected(client, test_engine, test_org, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
    other_project = await _make_project(test_engine, test_org)
    foreign_site = await _make_site(test_engine, test_org, other_project)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(foreign_site),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_inaccessible_project_rejected(client, test_engine, test_org, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
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
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(token))
    assert resp.status_code == 403


async def test_adjustment_reason_forbidden_for_non_elevated_role(
    client, test_engine, test_org, admin_ctx
):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
    site_engineer = await _make_user(test_engine, test_org, "site_engineer")
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("UPDATE users SET access_policy = CAST(:p AS jsonb) WHERE id = :id"),
            {"p": '{"mode": "all_projects", "projects": []}', "id": site_engineer},
        )
    token = _token(site_engineer, test_org, "site_engineer")
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "movement_reason": "ADJUSTMENT_IN",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(token))
    assert resp.status_code == 403


async def test_reversal_creates_offsetting_movement_and_preserves_original(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)
    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "100",
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

    original = await client.get(
        f"/materials/inflows/{receipt_id}", headers=_auth(admin_ctx["token"])
    )
    assert original.status_code == 200
    assert original.json()["quantity"] == "100.00"
    assert original.json()["movement_reason"] == "RECEIVED"

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["current_stock"] == "0.00"
    assert rows[0]["stock_state"] == "OUT_OF_STOCK"


async def test_ledger_running_balance(client, admin_ctx):
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)

    for qty, endpoint, reason in [
        ("50", "/materials/inflows", "RECEIVED"),
        ("20", "/materials/outflows", "CONSUMED"),
        ("10", "/materials/inflows", "RECEIVED"),
    ]:
        body = {
            "project_id": str(admin_ctx["project_id"]),
            "site_id": str(admin_ctx["site_id"]),
            "material_id": material_id,
            "unit_id": bags_id,
            "quantity": qty,
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


async def test_rest_path_unique_constraint_prevents_duplicate_movement(
    test_engine: AsyncEngine,
    admin_ctx,
):
    """The REST write path (router.py's create_inflow/create_outflow) has no
    idempotency_keys claim like the CQRS path -- its only guard against a
    retried POST double-posting into the ledger is migration 0310's
    UNIQUE(source_type, source_id, movement_type) constraint on
    material_movements. This test proves that constraint actually fires at the
    DB level: a second movement insert with the same (source_type, source_id,
    movement_type) triple must raise IntegrityError rather than silently
    landing a duplicate row.

    The realistic way the constraint bites: a retried inflow POST reuses the
    same receipt row_id (e.g. a client retrying with a fixed request id, or a
    connection-level redelivery). The router generates row_id per request, so
    the HTTP surface alone can't reproduce it -- this test seeds the first
    movement directly and then attempts the duplicate.
    """
    from sqlalchemy.exc import IntegrityError

    async with test_engine.connect() as conn:
        org_id = (
            await conn.execute(
                sa.text("SELECT organization_id FROM users WHERE id = :id"),
                {"id": admin_ctx["user_id"]},
            )
        ).scalar_one()
        bags_id = (
            await conn.execute(sa.text("SELECT id FROM units_of_measure WHERE code = 'bags'"))
        ).scalar_one()

    material_id = uuid.uuid4()
    receipt_id = uuid.uuid4()

    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO materials_catalog "
                "(id, organization_id, name, default_unit_id, is_active, created_by) "
                "VALUES (:id, :org_id, 'IdempotencyTestMat', :unit_id, true, :user_id)"
            ),
            {
                "id": material_id,
                "org_id": org_id,
                "unit_id": bags_id,
                "user_id": admin_ctx["user_id"],
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO material_receipts "
                "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                "unit_id, material_id, occurred_date, occurred_date_source, source, "
                "movement_reason, created_by) "
                "VALUES (:id, :org_id, :project_id, :site_id, 'IdempotencyTestMat', 10, 'bags', "
                ":unit_id, :material_id, :occurred_date, 'reported', 'web', 'RECEIVED', :user_id)"
            ),
            {
                "id": receipt_id,
                "org_id": org_id,
                "project_id": admin_ctx["project_id"],
                "site_id": admin_ctx["site_id"],
                "unit_id": bags_id,
                "material_id": material_id,
                "occurred_date": datetime.date.today(),
                "user_id": admin_ctx["user_id"],
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO material_movements "
                "(id, organization_id, project_id, site_id, material_id, unit_id, movement_type, "
                "quantity, occurred_at, source_type, source_id, recorded_by_user_id, created_at) "
                "VALUES (gen_random_uuid(), :org_id, :project_id, :site_id, :material_id, :unit_id, "
                "'RECEIPT', 10, now(), 'material_receipt', :source_id, :user_id, now())"
            ),
            {
                "org_id": org_id,
                "project_id": admin_ctx["project_id"],
                "site_id": admin_ctx["site_id"],
                "material_id": material_id,
                "unit_id": bags_id,
                "source_id": receipt_id,
                "user_id": admin_ctx["user_id"],
            },
        )

    with pytest.raises(IntegrityError):
        async with test_engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO material_movements "
                    "(id, organization_id, project_id, site_id, material_id, unit_id, "
                    "movement_type, quantity, occurred_at, source_type, source_id, "
                    "recorded_by_user_id, created_at) "
                    "VALUES (gen_random_uuid(), :org_id, :project_id, :site_id, :material_id, "
                    ":unit_id, 'RECEIPT', 10, now(), 'material_receipt', :source_id, :user_id, now())"
                ),
                {
                    "org_id": org_id,
                    "project_id": admin_ctx["project_id"],
                    "site_id": admin_ctx["site_id"],
                    "material_id": material_id,
                    "unit_id": bags_id,
                    "source_id": receipt_id,
                    "user_id": admin_ctx["user_id"],
                },
            )

    async with test_engine.connect() as conn:
        movement_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM material_movements "
                    "WHERE source_type = 'material_receipt' AND source_id = :id"
                ),
                {"id": receipt_id},
            )
        ).scalar_one()
        assert movement_count == 1, (
            "the UNIQUE guard must leave exactly one movement; the duplicate insert "
            "must not have partially landed despite the rolled-back transaction"
        )


async def test_inflow_with_unit_mismatched_to_stock_unit_rejected(client, admin_ctx):
    """The existing test_outflow_with_unit_mismatched_to_stock_unit_rejected
    covers the outflow path; the inflow path goes through the same
    _resolve_and_validate_material_unit gate (router.py:512) and must also
    reject a unit_id that doesn't match the material's Stock Unit. No unit
    conversion is supported in V1 -- a cement material tracked in bags must
    refuse an inflow reported in tons, not silently store it."""
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    tons_id = await _tons_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)

    body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": tons_id,  # Cement's Stock Unit is bags, not tons
        "quantity": "10",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 422


async def test_stock_unit_change_rejected_after_movement_exists(client, admin_ctx):
    """update_material (router.py:233) must refuse to change default_unit_id
    once any material_movements row references this material -- a material's
    tracking unit is fixed for its lifetime in V1 (no unit conversion).
    Existing test_delete_material_with_movements_rejected covers the delete
    lock; this covers the unit-change lock, which is the more common
    real-world temptation (admin renames 'bags' to 'sacks' mid-project)."""
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    tons_id = await _tons_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Rebar", tons_id)

    inflow_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": tons_id,
        "quantity": "10",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(
        "/materials/inflows", json=inflow_body, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 201

    resp = await client.patch(
        f"/materials/{material_id}",
        json={"default_unit_id": bags_id},  # attempt to switch tons -> bags
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 409
    assert "Stock Unit cannot change" in resp.json()["detail"]


async def test_stock_levels_derived_exclusively_from_movement_ledger(
    client, test_engine: AsyncEngine, admin_ctx
):
    """get_stock_levels (materials.py:303) must read ONLY from
    material_movements -- never from material_receipts/material_usage. The
    V2 design's whole point is that the ledger is the single source of stock
    truth; operational rows are history-only. If a future refactor regresses
    to SUM(receipts) - SUM(usage), stock would silently drift as orphan
    receipt rows (failed movement posts, manual backfills, etc.) leak in.

    This test seeds a material with one real inflow (quantity 10, which posts
    a matching movement) and one orphan material_receipts row (quantity 999,
    no movement). Inventory must read 10, not 1009 -- the orphan is
    structurally invisible to stock derivation."""
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)

    orphan_receipt_id = uuid.uuid4()
    async with test_engine.connect() as conn:
        org_id = (
            await conn.execute(
                sa.text("SELECT organization_id FROM users WHERE id = :id"),
                {"id": admin_ctx["user_id"]},
            )
        ).scalar_one()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO material_receipts "
                "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                "unit_id, material_id, occurred_date, occurred_date_source, source, "
                "movement_reason, created_by) "
                "VALUES (:id, :org_id, :project_id, :site_id, 'Cement', 999, 'bags', "
                ":unit_id, :material_id, :occurred_date, 'reported', 'manual', 'RECEIVED', :user_id)"
            ),
            {
                "id": orphan_receipt_id,
                "org_id": org_id,
                "project_id": admin_ctx["project_id"],
                "site_id": admin_ctx["site_id"],
                "unit_id": bags_id,
                "material_id": material_id,
                "occurred_date": datetime.date.today(),
                "user_id": admin_ctx["user_id"],
            },
        )

    real_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post("/materials/inflows", json=real_body, headers=_auth(admin_ctx["token"]))
    assert resp.status_code == 201

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 200
    rows = resp.json()
    cement_row = next(r for r in rows if r["material_name"] == "Cement")
    assert cement_row["current_stock"] == "10.00", (
        "stock must be derived from material_movements only; the orphan receipt row "
        "(quantity 999, no matching movement) must be invisible to get_stock_levels"
    )

    async with test_engine.connect() as conn:
        orphan_movement_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM material_movements WHERE source_id = :id"
                ),
                {"id": orphan_receipt_id},
            )
        ).scalar_one()
        assert orphan_movement_count == 0, (
            "the orphan receipt must have no movement -- this test's premise"
        )


async def test_reversal_produces_opposite_movement_and_net_zero_stock(
    client, test_engine: AsyncEngine, admin_ctx
):
    """The insert-only/reversal convention (0270 + 0300 + posting.py:11-15)
    says corrections never edit or delete a movement -- they post an opposite-
    direction movement with reversal_of_movement_id set. So a receipt of 10
    followed by its reversal must leave the ledger summing to exactly 0. The
    existing test_reversal_creates_offsetting_movement_and_preserves_original
    proves the original row survives and a new offsetting row appears; this
    test asserts the load-bearing net-zero stock invariant that follows."""
    bags_id = await _bags_unit_id(client, admin_ctx["token"])
    material_id = await _make_material(client, admin_ctx["token"], "Cement", bags_id)

    inflow_body = {
        "project_id": str(admin_ctx["project_id"]),
        "site_id": str(admin_ctx["site_id"]),
        "material_id": material_id,
        "unit_id": bags_id,
        "quantity": "10",
        "movement_reason": "RECEIVED",
        "occurred_date": str(datetime.date.today()),
    }
    resp = await client.post(
        "/materials/inflows", json=inflow_body, headers=_auth(admin_ctx["token"])
    )
    assert resp.status_code == 201
    receipt_id = resp.json()["id"]

    resp = await client.post(
        f"/materials/inflows/{receipt_id}/reverse",
        json={},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 201

    resp = await client.get(
        "/materials/inventory",
        params={"project_id": str(admin_ctx["project_id"])},
        headers=_auth(admin_ctx["token"]),
    )
    assert resp.status_code == 200
    rows = resp.json()
    cement_row = next(r for r in rows if r["material_name"] == "Cement")
    assert cement_row["current_stock"] == "0.00", (
        "a receipt reversed by its opposite-direction ISSUE must net to zero"
    )
    assert cement_row["stock_state"] == "OUT_OF_STOCK"

    async with test_engine.connect() as conn:
        original_movement = (
            await conn.execute(
                sa.text(
                    "SELECT id FROM material_movements "
                    "WHERE source_type = 'material_receipt' AND source_id = :id "
                    "AND reversal_of_movement_id IS NULL"
                ),
                {"id": receipt_id},
            )
        ).scalar_one()

        reversal_movement = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT movement_type, reversal_of_movement_id "
                        "FROM material_movements "
                        "WHERE reversal_of_movement_id = :orig_id"
                    ),
                    {"orig_id": original_movement},
                )
            )
            .mappings()
            .one()
        )
        assert reversal_movement["movement_type"] == "ISSUE", (
            "reversing a RECEIPT must post an ISSUE, not another RECEIPT"
        )
        assert reversal_movement["reversal_of_movement_id"] == original_movement
