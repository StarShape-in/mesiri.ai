"""Add materials_catalog — the Material master list (v1 Material domain, pt. 2).

Part 1 (0090) recorded receipts/usage with free-text `material_name`. This
adds the catalog those names refer to, so reports can group/aggregate by a stable
`material_id` instead of fragile string matching.

Scope is deliberately narrow — catalog ONLY:
  - No inventory_stock / stock-on-hand table. Balanced stock requires every
    movement source (receipts, usage, transfers, adjustments, procurement GRNs)
    to flow into the balance. Procurement is a later module; building a balance
    table now would mean refactoring it back in. Defer until sources are stable.
  - No supplier / sku-as-entity model — `supplier` stays free text on receipts.
  - No unit-of-measure conversions — `unit` stays free text.

`material_id` is added to material_receipts and material_usage as a NULLABLE FK.
Existing free-text rows continue to work; new writes should populate it when a
catalog match exists. A backfill step seeds catalog rows from the distinct
material_name values already present in receipts/usage, so the catalog is not
empty on day one.

Revision ID: 0180
Revises: 0170
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0180"
down_revision = "0170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials_catalog",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("default_unit", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_materials_catalog_org_name",
        ),
    )
    op.create_index(
        "ix_materials_catalog_org",
        "materials_catalog",
        ["organization_id"],
    )
    op.create_index(
        "ix_materials_catalog_category",
        "materials_catalog",
        ["organization_id", "category"],
    )

    # Link existing event tables to the catalog. Nullable so historical rows and
    # free-text flows keep working during the transition.
    op.add_column(
        "material_receipts",
        sa.Column("material_id", sa.UUID(as_uuid=True), sa.ForeignKey("materials_catalog.id"), nullable=True),
    )
    op.add_column(
        "material_usage",
        sa.Column("material_id", sa.UUID(as_uuid=True), sa.ForeignKey("materials_catalog.id"), nullable=True),
    )
    op.create_index(
        "ix_material_receipts_material_id",
        "material_receipts",
        ["material_id"],
    )
    op.create_index(
        "ix_material_usage_material_id",
        "material_usage",
        ["material_id"],
    )

    # Backfill: seed one catalog row per distinct material_name already recorded,
    # grouped by organization. Keeps name->material_id joinable for history.
    op.execute(
        """
        INSERT INTO materials_catalog (id, organization_id, name, default_unit, created_by)
        SELECT
            gen_random_uuid(),
            organization_id,
            name,
            MAX(unit),
            (MIN(created_by::text))::uuid
        FROM (
            SELECT organization_id, material_name AS name, unit, created_by FROM material_receipts
            UNION ALL
            SELECT organization_id, material_name AS name, unit, created_by FROM material_usage
        ) AS combined
        WHERE name IS NOT NULL AND name <> ''
        GROUP BY organization_id, name
        ON CONFLICT DO NOTHING
        """
    )

    # Link historical rows back to the catalog by name+org, where a match exists.
    op.execute(
        """
        UPDATE material_receipts r
        SET material_id = c.id
        FROM materials_catalog c
        WHERE c.organization_id = r.organization_id
          AND c.name = r.material_name
        """
    )
    op.execute(
        """
        UPDATE material_usage u
        SET material_id = c.id
        FROM materials_catalog c
        WHERE c.organization_id = u.organization_id
          AND c.name = u.material_name
        """
    )


def downgrade() -> None:
    op.drop_index("ix_material_usage_material_id", table_name="material_usage")
    op.drop_column("material_usage", "material_id")
    op.drop_index("ix_material_receipts_material_id", table_name="material_receipts")
    op.drop_column("material_receipts", "material_id")

    op.drop_index("ix_materials_catalog_category", table_name="materials_catalog")
    op.drop_index("ix_materials_catalog_org", table_name="materials_catalog")
    op.drop_table("materials_catalog")
