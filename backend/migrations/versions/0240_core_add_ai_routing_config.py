"""Add AI active routes and provider secrets tables.

Revision ID: 0240
Revises: 0230
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0240"
down_revision = "0230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ai_active_routes ---
    op.create_table(
        "ai_active_routes",
        sa.Column("capability", sa.String(), primary_key=True),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed default active routes
    op.execute(
        "INSERT INTO ai_active_routes (capability, provider_id, model) VALUES "
        "('voice', 'sarvam', 'saaras:v2.5'),"
        "('extraction', 'gemini', 'gemini-2.5-flash'),"
        "('vision', 'gemini', 'gemini-2.5-flash'),"
        "('translation', 'gemini', 'gemini-2.5-flash')"
    )

    # --- ai_provider_secrets ---
    op.create_table(
        "ai_provider_secrets",
        sa.Column("provider_id", sa.String(), primary_key=True),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_secrets")
    op.drop_table("ai_active_routes")
