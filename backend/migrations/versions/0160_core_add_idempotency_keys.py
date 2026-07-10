"""Add idempotency_keys — command-level idempotency (distinct from message dedup).

The ingress DeduplicationStore (Redis, 24h TTL) prevents reprocessing the same
WhatsApp message_id. This table is a different guarantee: it makes an
Application Command safe to retry (e.g. after a crash mid-transaction) without
double-writing a domain row. `result` caches the outcome so a retry can return
the original result instead of re-executing.

Revision ID: 0160
Revises: 0150
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0160"
down_revision = "0150"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("command_type", sa.String(), nullable=False),
        sa.Column("result", JSONB, nullable=True),
        # Status: in_progress | completed | failed
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_idempotency_keys_command_type", "idempotency_keys", ["command_type"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_command_type", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
