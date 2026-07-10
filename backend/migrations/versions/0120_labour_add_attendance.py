"""Add labour_attendance and labour_attendance_entries — v1 Labour domain.

Header + optional-detail pattern: labour_attendance always holds an aggregate
headcount for a site/day (how most WhatsApp reports arrive — "12 masons, 5
helpers"). labour_attendance_entries only exists when the sender actually named
individual workers; headcount_total is either reported directly or derived
from entry count when entries are present.

This table is intentionally v1-minimal. Full Workforce (shifts, wages,
contracts) is a later module and will very likely supersede this table rather
than extend it — do not over-build here.

Revision ID: 0120
Revises: 0110
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0120"
down_revision = "0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "labour_attendance",
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
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("headcount_total", sa.Integer(), nullable=False),
        sa.Column("headcount_by_role", JSONB, nullable=True),
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
        sa.UniqueConstraint("site_id", "occurred_date", name="uq_labour_attendance_site_date"),
    )
    op.create_index(
        "ix_labour_attendance_org_project", "labour_attendance", ["organization_id", "project_id"]
    )
    op.create_index("ix_labour_attendance_occurred_date", "labour_attendance", ["occurred_date"])
    op.create_index("ix_labour_attendance_correlation_id", "labour_attendance", ["correlation_id"])

    op.create_table(
        "labour_attendance_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attendance_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("labour_attendance.id"),
            nullable=False,
        ),
        sa.Column("worker_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("hours_worked", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_labour_attendance_entries_attendance_id",
        "labour_attendance_entries",
        ["attendance_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_labour_attendance_entries_attendance_id", table_name="labour_attendance_entries"
    )
    op.drop_table("labour_attendance_entries")

    op.drop_index("ix_labour_attendance_correlation_id", table_name="labour_attendance")
    op.drop_index("ix_labour_attendance_occurred_date", table_name="labour_attendance")
    op.drop_index("ix_labour_attendance_org_project", table_name="labour_attendance")
    op.drop_table("labour_attendance")
