"""Add outbox_events table — the shared event-publishing foundation.

Every domain module (Material, Equipment, Labour, Expense, Finance) writes its
business row and an outbox_events row in the same transaction. A separate
publisher (mesiri.events.outbox.publisher) drains unpublished rows to Redis
Streams. This guarantees no Domain Event is ever lost, even on a crash between
write and publish (architecture rule: "every business event is published via
the outbox; none are ever lost").

Revision ID: 1a2b3c4d5e6f
Revises: f7g8h9i0j1k2
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "1a2b3c4d5e6f"
down_revision = "f7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("aggregate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_unpublished",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_index(
        "ix_outbox_events_aggregate", "outbox_events", ["aggregate_type", "aggregate_id"]
    )
    op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_correlation_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_unpublished", table_name="outbox_events")
    op.drop_table("outbox_events")
