"""Add interactions — human-in-the-loop confirmation table (M7).

Backs WorkflowStateReadPort.get_pending_interaction, which is fake-only today.
A confirmation/clarification/correction request sent to the user; the user's
reply re-enters via ingress and is matched back to the pending row here by
`related_message_id` / `correlation_id`.

Revision ID: 0140
Revises: 0130
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0140"
down_revision = "0130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interactions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_instance_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id"),
            nullable=True,
        ),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        # Kind: confirmation | clarification | correction
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("related_message_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # Status: pending | resolved | expired
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interactions_user_status", "interactions", ["user_id", "status"])
    op.create_index("ix_interactions_correlation_id", "interactions", ["correlation_id"])
    op.create_index(
        "ix_interactions_workflow_instance_id", "interactions", ["workflow_instance_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_interactions_workflow_instance_id", table_name="interactions")
    op.drop_index("ix_interactions_correlation_id", table_name="interactions")
    op.drop_index("ix_interactions_user_status", table_name="interactions")
    op.drop_table("interactions")
