"""Add material_movements — the immutable stock ledger (Materials V2).

`material_receipts`/`material_usage` remain the operational records of what
was *reported* (one row per WhatsApp/dashboard event, unchanged shape — no
receipt_items/usage_items). `material_movements` becomes the only source of
stock truth: every receipt produces exactly one RECEIPT movement, every usage
exactly one ISSUE movement, and stock is derived solely by summing this
table — never by re-deriving SUM(receipts) - SUM(usage) from the operational
tables directly (that computation becomes read-path-only history until the
read paths are cut over in application code; see docs/plan).

This mirrors the insert-only/reversal convention already established by
0270 (`reverses_movement_id`): movements are never UPDATE'd or DELETE'd,
only corrected by inserting a new movement with `reversal_of_movement_id`
set, carrying the OPPOSITE `movement_type` of the movement it reverses (a
correction to a RECEIPT posts an ISSUE, and vice versa) — the same
opposite-direction-row convention 0270 already uses for
material_receipts/material_usage reversals.

`movement_type` is a small fixed vocabulary (RECEIPT, ISSUE for V1,
extensible later) validated at the application layer, matching this
codebase's existing convention for RECEIPT_REASONS/USAGE_REASONS
(domains/materials/validation.py) rather than a DB CHECK constraint.

`source_type`/`source_id` point back at the originating material_receipts or
material_usage row (polymorphic — no FK, since it spans two tables). This is
deliberately generic so a future Procurement module can post movements with
new source_types (e.g. "goods_receipt") without any schema change here —
Materials/Stock must never depend on Procurement; Procurement depends on
Materials/Stock by posting into this same ledger.

`material_id`/`unit_id` are NOT NULL from the start (stricter than the
nullable FKs added to material_receipts/material_usage by 0180/0290) since
every movement is created going forward only after catalog/unit resolution
succeeds — there is no free-text period for this table to backfill through.

Backfills one RECEIPT movement per existing material_receipts row and one
ISSUE movement per existing material_usage row, using each row's resolved
material_id/unit_id. 0180's original catalog backfill and 0290's unit
backfill both matched by exact string equality, which misses case/whitespace
variants present in real production data — this migration self-heals any
still-unresolved material_id with a case/whitespace-insensitive catalog
lookup, falling back to creating a new catalog entry from the row's own
reported name (mirroring 0290's fallback-unit creation), rather than
aborting a deploy on data it can resolve or safely fall back for.

Revision ID: 0300
Revises: 0290
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0300"
down_revision = "0290"
branch_labels = None
depends_on = None

MOVEMENT_TYPES = ("RECEIPT", "ISSUE")


def upgrade() -> None:
    op.create_table(
        "material_movements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column(
            "material_id", sa.UUID(as_uuid=True), sa.ForeignKey("materials_catalog.id"), nullable=False
        ),
        sa.Column(
            "unit_id", sa.UUID(as_uuid=True), sa.ForeignKey("units_of_measure.id"), nullable=False
        ),
        sa.Column("movement_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "recorded_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "reversal_of_movement_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_movements.id"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_material_movements_org_project_site_material",
        "material_movements",
        ["organization_id", "project_id", "site_id", "material_id"],
    )
    op.create_index("ix_material_movements_source", "material_movements", ["source_type", "source_id"])
    op.create_index("ix_material_movements_material_id", "material_movements", ["material_id"])

    conn = op.get_bind()

    # 0180's original catalog backfill (and 0290's unit backfill) matched by
    # exact string equality, which misses case/whitespace variants (e.g.
    # "Cement" reported once, "cement" another time) -- production has rows
    # like this. Same principle as 0290's fallback-unit fix: self-heal rather
    # than abort a deploy on data we can resolve or safely fall back for.
    for table in ("material_receipts", "material_usage"):
        # Case/whitespace-insensitive catalog link for rows 0180 missed.
        conn.execute(
            sa.text(
                f"UPDATE {table} t SET material_id = c.id "  # noqa: S608
                "FROM materials_catalog c "
                "WHERE t.material_id IS NULL AND c.organization_id = t.organization_id "
                "AND lower(trim(c.name)) = lower(trim(t.material_name))"
            )
        )
        # Anything still unresolved (no catalog entry at all, even case-
        # insensitively) gets one created from the row's own reported name --
        # mirrors 0290's fallback-unit creation. Grouped by (org, trimmed
        # lowercased name) so repeated reports of the same never-cataloged
        # material collapse onto one new catalog row, not one per row.
        uncataloged = conn.execute(
            sa.text(
                f"SELECT DISTINCT organization_id, "  # noqa: S608
                f"COALESCE(NULLIF(trim(material_name), ''), 'Unresolved Material'), created_by "
                f"FROM {table} WHERE material_id IS NULL"
            )
        ).fetchall()
        for org_id, name, created_by in uncataloged:
            new_material_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO materials_catalog (id, organization_id, name, is_active, created_by) "
                    "VALUES (:id, :org_id, :name, true, :created_by) "
                    "ON CONFLICT (organization_id, name) DO NOTHING"
                ),
                {"id": new_material_id, "org_id": org_id, "name": name, "created_by": created_by},
            )
            conn.execute(
                sa.text(
                    f"UPDATE {table} t SET material_id = c.id "  # noqa: S608
                    "FROM materials_catalog c "
                    "WHERE t.material_id IS NULL AND c.organization_id = :org_id "
                    "AND lower(trim(c.name)) = lower(trim(:name)) AND t.organization_id = :org_id "
                    f"AND COALESCE(NULLIF(trim(t.material_name), ''), 'Unresolved Material') = :name"
                ),
                {"org_id": org_id, "name": name},
            )

        # unit_id should already be fully resolved by 0290's fallback-unit
        # creation, but re-check defensively — this is the true "should be
        # unreachable" guard now (material_id is self-healed above; unit_id
        # was self-healed in 0290).
        unresolved = conn.execute(
            sa.text(
                f"SELECT id FROM {table} WHERE material_id IS NULL OR unit_id IS NULL LIMIT 5"  # noqa: S608
            )
        ).fetchall()
        if unresolved:
            ids = ", ".join(str(row[0]) for row in unresolved)
            raise RuntimeError(
                f"Migration 0300: {table} has rows with unresolved material_id/unit_id "
                f"(e.g. {ids}) after self-healing — investigate this data manually."
            )

    conn.execute(
        sa.text(
            """
            INSERT INTO material_movements (
                id, organization_id, project_id, site_id, material_id, unit_id,
                movement_type, quantity, occurred_at, source_type, source_id,
                recorded_by_user_id, created_at
            )
            SELECT
                gen_random_uuid(), organization_id, project_id, site_id, material_id, unit_id,
                'RECEIPT', quantity,
                (occurred_date + COALESCE(occurred_time, TIME '00:00:00')) AT TIME ZONE 'UTC',
                'material_receipt', id, created_by, created_at
            FROM material_receipts
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO material_movements (
                id, organization_id, project_id, site_id, material_id, unit_id,
                movement_type, quantity, occurred_at, source_type, source_id,
                recorded_by_user_id, created_at
            )
            SELECT
                gen_random_uuid(), organization_id, project_id, site_id, material_id, unit_id,
                'ISSUE', quantity,
                (occurred_date + COALESCE(occurred_time, TIME '00:00:00')) AT TIME ZONE 'UTC',
                'material_usage', id, created_by, created_at
            FROM material_usage
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_material_movements_material_id", table_name="material_movements")
    op.drop_index("ix_material_movements_source", table_name="material_movements")
    op.drop_index("ix_material_movements_org_project_site_material", table_name="material_movements")
    op.drop_table("material_movements")
