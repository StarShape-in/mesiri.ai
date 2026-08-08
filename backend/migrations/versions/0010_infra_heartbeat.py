"""M1 infrastructure baseline: infra_heartbeat table.

Creates the single infrastructure table needed to prove the persistence path is
alive (used by the M1 golden scenario for a real write+read round-trip). No
domain schemas (expenses, equipment, materials, labour, approvals, ...) are
created here — those belong to later milestones.

Revision ID: 0010
Revises:
Create Date: 2026-07-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "infra_heartbeat",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "observed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("infra_heartbeat")
