"""Add equipment_events — v1 Equipment & Machinery domain.

One table, not several: on-site/departed/usage/movement/refuel are point-in-
time state transitions of the *same* equipment entity (unlike Material, which
splits arrived/used because those carry genuinely different optional fields).
`event_type` distinguishes them; fuel_* and from/to_site_id columns are only
populated for the event types they apply to.

Revision ID: 0110
Revises: 0100
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0110"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("equipment_name", sa.String(), nullable=False),
        sa.Column("equipment_type", sa.String(), nullable=True),
        # Event type: arrived | departed | usage_started | usage_ended | moved | refueled
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("duration_hours", sa.Numeric(6, 2), nullable=True),
        # Movement events only.
        sa.Column("from_site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("to_site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        # Refuel events only.
        sa.Column("fuel_quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("fuel_unit", sa.String(), nullable=True),
        sa.Column("fuel_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "paid_from_account_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("finance_accounts.id"),
            nullable=True,
        ),
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("occurred_time", sa.Time(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
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
    )
    op.create_index(
        "ix_equipment_events_org_project", "equipment_events", ["organization_id", "project_id"]
    )
    op.create_index("ix_equipment_events_site_id", "equipment_events", ["site_id"])
    op.create_index("ix_equipment_events_occurred_date", "equipment_events", ["occurred_date"])
    op.create_index("ix_equipment_events_correlation_id", "equipment_events", ["correlation_id"])
    op.create_index(
        "ix_equipment_events_equipment_name",
        "equipment_events",
        ["organization_id", "equipment_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_equipment_events_equipment_name", table_name="equipment_events")
    op.drop_index("ix_equipment_events_correlation_id", table_name="equipment_events")
    op.drop_index("ix_equipment_events_occurred_date", table_name="equipment_events")
    op.drop_index("ix_equipment_events_site_id", table_name="equipment_events")
    op.drop_index("ix_equipment_events_org_project", table_name="equipment_events")
    op.drop_table("equipment_events")
