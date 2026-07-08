"""Add material_receipts and material_usage — v1 Material domain (proof of architecture).

Two tables, not one with a direction flag: "arrived" and "used" carry different
optional fields (supplier/cost vs work_item) and are reported/confirmed as
distinct conversational flows. `material_id` (FK to a future materials_catalog /
inventory table) is deliberately NOT added yet — Procurement/Inventory is a
later module; adding a dangling FK now would be premature.

Revision ID: 0090
Revises: 0080
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0090"
down_revision = "0080"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "material_receipts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("material_name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("supplier", sa.String(), nullable=True),
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("occurred_time", sa.Time(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
        *_audit_columns(),
    )
    op.create_index("ix_material_receipts_org_project", "material_receipts", ["organization_id", "project_id"])
    op.create_index("ix_material_receipts_site_id", "material_receipts", ["site_id"])
    op.create_index("ix_material_receipts_occurred_date", "material_receipts", ["occurred_date"])
    op.create_index("ix_material_receipts_correlation_id", "material_receipts", ["correlation_id"])

    op.create_table(
        "material_usage",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("material_name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("work_item", sa.String(), nullable=True),
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("occurred_time", sa.Time(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
        *_audit_columns(),
    )
    op.create_index("ix_material_usage_org_project", "material_usage", ["organization_id", "project_id"])
    op.create_index("ix_material_usage_site_id", "material_usage", ["site_id"])
    op.create_index("ix_material_usage_occurred_date", "material_usage", ["occurred_date"])
    op.create_index("ix_material_usage_correlation_id", "material_usage", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_material_usage_correlation_id", table_name="material_usage")
    op.drop_index("ix_material_usage_occurred_date", table_name="material_usage")
    op.drop_index("ix_material_usage_site_id", table_name="material_usage")
    op.drop_index("ix_material_usage_org_project", table_name="material_usage")
    op.drop_table("material_usage")

    op.drop_index("ix_material_receipts_correlation_id", table_name="material_receipts")
    op.drop_index("ix_material_receipts_occurred_date", table_name="material_receipts")
    op.drop_index("ix_material_receipts_site_id", table_name="material_receipts")
    op.drop_index("ix_material_receipts_org_project", table_name="material_receipts")
    op.drop_table("material_receipts")
