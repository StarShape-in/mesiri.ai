"""Add optimistic-lock version + single-active-confirmation invariant to workflow_instances (M7).

M7 resumes an AWAITING_CONFIRMATION workflow exactly once:
- `version` (int) backs an optimistic-lock conditional UPDATE so duplicate
  WhatsApp deliveries / simultaneous replies cannot transition a workflow twice.
- A partial unique index enforces the single-active invariant: a user may have
  at most one workflow in phase 'awaiting_confirmation' at a time. This is the
  hard DB guarantee behind the app-level pre-check in WorkflowRuntime.start().

Revision ID: 0200
Revises: 0195
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0200"
down_revision = "0195"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_instances",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "uq_workflow_instances_one_awaiting_per_user",
        "workflow_instances",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("phase = 'awaiting_confirmation'"),
    )


def downgrade() -> None:
    op.drop_index("uq_workflow_instances_one_awaiting_per_user", table_name="workflow_instances")
    op.drop_column("workflow_instances", "version")
