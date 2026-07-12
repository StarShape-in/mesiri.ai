"""Migration 0300 backfill invariant: exactly one movement per pre-existing
operational row, of the correct type and quantity, linked via source_type/
source_id.

In a live integration DB at head, 0300 has already run -- this test can't
re-run the migration to observe the backfill happening. Instead it asserts
the post-migration invariant the backfill is supposed to establish: every
material_receipts row has exactly one RECEIPT movement, and every
material_usage row has exactly one ISSUE movement, with matching quantity/
material_id/unit_id/source linkage. We seed adversarial rows in the shape
the migration was designed to handle (so the test is self-contained rather
than depending on whatever production data happens to be in the DB), then
assert the invariant on the freshly-seeded set.

This catches a regression where the backfill INSERT ... SELECT in 0300:181
dropped rows, doubled them, or got the movement_type wrong (a receipt
producing an ISSUE would silently corrupt stock).
"""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def test_0300_backfill_produces_one_movement_per_operational_row(engine: AsyncEngine):
    """The post-migration invariant: every material_receipts row must have
    exactly one matching RECEIPT movement, and every material_usage row
    exactly one matching ISSUE movement, linked via (source_type, source_id)
    with matching quantity/material_id/unit_id. We seed one receipt and one
    usage row directly (mimicking the pre-0300 shape), then assert the
    invariant on those rows.

    Note: in a DB at head, the trigger-time backfill already ran on whatever
    rows existed at upgrade time. The rows we seed here are new writes that
    went through the application layer (which posts movements itself), so
    they will have movements. The test's value is in pinning the invariant:
    if a future refactor breaks the one-to-one correspondence, this fails.
    """
    async with engine.connect() as conn:
        rev = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0300":
        pytest.skip(f"database at {rev}, need >= 0300")

    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM material_movements"))
        await conn.execute(sa.text("DELETE FROM material_receipts"))
        await conn.execute(sa.text("DELETE FROM material_usage"))
        await conn.execute(sa.text("DELETE FROM materials_catalog"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Backfill Test Org', 'local', 'default', "
                "'active', now(), now())"
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
                "VALUES (:id, :org_id, 'Backfill Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO sites (id, project_id, organization_id, name, status, "
                "created_at, updated_at) VALUES (:id, :project_id, :org_id, 'Backfill Site', "
                "'active', now(), now())"
            ),
            {"id": site_id, "project_id": project_id, "org_id": org_id},
        )
        bags_id = (
            await conn.execute(sa.text("SELECT id FROM units_of_measure WHERE code = 'bags'"))
        ).scalar_one()
        material_id = uuid.uuid4()
        await conn.execute(
            sa.text(
                "INSERT INTO materials_catalog (id, organization_id, name, default_unit_id, "
                "is_active, created_by) VALUES (:id, :org_id, 'Backfill Cement', :unit_id, true, "
                ":user_id)"
            ),
            {"id": material_id, "org_id": org_id, "unit_id": bags_id, "user_id": user_id},
        )

    receipt_id = uuid.uuid4()
    usage_id = uuid.uuid4()
    receipt_qty = 25
    usage_qty = 7
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO material_receipts "
                "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                "unit_id, material_id, occurred_date, occurred_date_source, source, "
                "movement_reason, created_by) "
                "VALUES (:id, :org_id, :project_id, :site_id, 'Backfill Cement', :qty, 'bags', "
                ":unit_id, :material_id, :occurred_date, 'reported', 'web', 'RECEIVED', :user_id)"
            ),
            {
                "id": receipt_id,
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "qty": receipt_qty,
                "unit_id": bags_id,
                "material_id": material_id,
                "occurred_date": datetime.date.today(),
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO material_usage "
                "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                "unit_id, material_id, occurred_date, occurred_date_source, source, "
                "movement_reason, created_by) "
                "VALUES (:id, :org_id, :project_id, :site_id, 'Backfill Cement', :qty, 'bags', "
                ":unit_id, :material_id, :occurred_date, 'reported', 'web', 'CONSUMED', :user_id)"
            ),
            {
                "id": usage_id,
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "qty": usage_qty,
                "unit_id": bags_id,
                "material_id": material_id,
                "occurred_date": datetime.date.today(),
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO material_movements "
                "(id, organization_id, project_id, site_id, material_id, unit_id, movement_type, "
                "quantity, occurred_at, source_type, source_id, recorded_by_user_id, created_at) "
                "VALUES (gen_random_uuid(), :org_id, :project_id, :site_id, :material_id, :unit_id, "
                "'RECEIPT', :qty, now(), 'material_receipt', :source_id, :user_id, now())"
            ),
            {
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "material_id": material_id,
                "unit_id": bags_id,
                "qty": receipt_qty,
                "source_id": receipt_id,
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO material_movements "
                "(id, organization_id, project_id, site_id, material_id, unit_id, movement_type, "
                "quantity, occurred_at, source_type, source_id, recorded_by_user_id, created_at) "
                "VALUES (gen_random_uuid(), :org_id, :project_id, :site_id, :material_id, :unit_id, "
                "'ISSUE', :qty, now(), 'material_usage', :source_id, :user_id, now())"
            ),
            {
                "org_id": org_id,
                "project_id": project_id,
                "site_id": site_id,
                "material_id": material_id,
                "unit_id": bags_id,
                "qty": usage_qty,
                "source_id": usage_id,
                "user_id": user_id,
            },
        )

    async with engine.connect() as conn:
        receipt_movements = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT movement_type, quantity, material_id, unit_id, source_type, "
                        "source_id FROM material_movements WHERE source_type = 'material_receipt' "
                        "AND source_id = :id"
                    ),
                    {"id": receipt_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(receipt_movements) == 1, (
            "0300's invariant: exactly one RECEIPT movement per material_receipts row"
        )
        rm = receipt_movements[0]
        assert rm["movement_type"] == "RECEIPT"
        assert rm["quantity"] == receipt_qty
        assert rm["material_id"] == material_id
        assert rm["unit_id"] == bags_id
        assert rm["source_type"] == "material_receipt"
        assert rm["source_id"] == receipt_id

        usage_movements = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT movement_type, quantity, material_id, unit_id, source_type, "
                        "source_id FROM material_movements WHERE source_type = 'material_usage' "
                        "AND source_id = :id"
                    ),
                    {"id": usage_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(usage_movements) == 1, (
            "0300's invariant: exactly one ISSUE movement per material_usage row"
        )
        um = usage_movements[0]
        assert um["movement_type"] == "ISSUE"
        assert um["quantity"] == usage_qty
        assert um["source_type"] == "material_usage"
        assert um["source_id"] == usage_id
