"""Add event_consumer_checkpoints -- per-consumer outbox read progress.

`outbox_events.published_at` is a single boolean-ish marker shared by every
reader (timeline_projector.py). That was fine while timeline_projector was
the only consumer, but #9 Notifications and #17 Search Index both need to
read the SAME outbox stream independently -- if either one "published" a row
by setting published_at, the OTHER consumer would never see it. This table
gives every NEW consumer its own progress marker, keyed by
(consumer_name, event_id), without touching outbox_events.published_at or
timeline_projector.py's proven mechanism at all -- that consumer keeps
working exactly as before.

Anti-join read pattern (see events/consumers/registry.py):

    SELECT oe.* FROM outbox_events oe
    WHERE NOT EXISTS (
        SELECT 1 FROM event_consumer_checkpoints ecp
        WHERE ecp.consumer_name = :name AND ecp.event_id = oe.id
    )
    ORDER BY oe.created_at
    LIMIT :batch
    FOR UPDATE OF oe SKIP LOCKED

FOR UPDATE OF oe SKIP LOCKED still guards against the SAME consumer running
twice concurrently (overlapping cron invocations) exactly like
timeline_projector's own docstring describes; a different consumer_name
briefly blocking on another consumer's held lock is a one-batch delay, not a
correctness issue, since each drain transaction is short-lived.

Revision ID: 0450
Revises: 0440
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0450"
down_revision = "0440"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "event_consumer_checkpoints" in inspector.get_table_names():
        # Idempotent upgrade -- same production-incident defense as 0420's
        # _create_enum_if_not_exists: a deploy that partially applies this
        # migration and fails must not be permanently stuck retrying the
        # same DuplicateTable error forever after.
        return

    op.create_table(
        "event_consumer_checkpoints",
        sa.Column("consumer_name", sa.String(), primary_key=True),
        sa.Column("event_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Supports the anti-join's WHERE NOT EXISTS lookup and the ORDER BY
    # oe.created_at outer query alike -- (event_id) alone would work for the
    # anti-join, but the primary key already covers that; this index is for
    # "how far along is consumer X" operational queries.
    op.create_index(
        "ix_event_consumer_checkpoints_consumer_processed",
        "event_consumer_checkpoints",
        ["consumer_name", "processed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_consumer_checkpoints_consumer_processed",
        table_name="event_consumer_checkpoints",
    )
    op.drop_table("event_consumer_checkpoints")
