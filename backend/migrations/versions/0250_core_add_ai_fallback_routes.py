"""Add fallback columns to AI active routes table.

Revision ID: 0250
Revises: 0240
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0250"
down_revision = "0240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_active_routes",
        sa.Column("fallback_provider_id", sa.String(), nullable=True),
    )
    op.add_column(
        "ai_active_routes",
        sa.Column("fallback_model", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_active_routes", "fallback_model")
    op.drop_column("ai_active_routes", "fallback_provider_id")
