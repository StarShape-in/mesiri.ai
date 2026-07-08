"""Add timeline_entries — the read-model projection of confirmed Domain Events.

Per the architecture: "Downstream systems react to Domain Events only — never
query business tables directly." A consumer drains outbox_events and projects
each confirmed event into a row here; the dashboard/timeline UI reads only
this table, never material_receipts/expenses/etc. directly.

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "9c0d1e2f3a4b"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timeline_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # Traceability back to the row that produced this projection.
        sa.Column("source_aggregate_type", sa.String(), nullable=False),
        sa.Column("source_aggregate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_timeline_entries_org_project", "timeline_entries", ["organization_id", "project_id"])
    op.create_index("ix_timeline_entries_site_id", "timeline_entries", ["site_id"])
    op.create_index("ix_timeline_entries_occurred_at", "timeline_entries", ["occurred_at"])
    op.create_index(
        "ix_timeline_entries_source", "timeline_entries", ["source_aggregate_type", "source_aggregate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_entries_source", table_name="timeline_entries")
    op.drop_index("ix_timeline_entries_occurred_at", table_name="timeline_entries")
    op.drop_index("ix_timeline_entries_site_id", table_name="timeline_entries")
    op.drop_index("ix_timeline_entries_org_project", table_name="timeline_entries")
    op.drop_table("timeline_entries")
