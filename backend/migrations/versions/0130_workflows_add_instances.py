"""Add workflow_instances — persists LangGraph conversation state (M6).

Backs WorkflowStateReadPort.get_active_workflow, which is fake-only today.
`state` holds the LangGraph checkpoint payload; the Workflow Runtime owns its
shape entirely (this table is intentionally opaque — no domain rules leak in
here, matching the architecture rule "LangGraph never imports SQL, Postgres,
or a repository": the runtime writes through a repository adapter, not
directly).

Revision ID: 0130
Revises: 0120
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0130"
down_revision = "0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workflow_key", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("state", JSONB, nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # Status: active | completed | abandoned
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_workflow_instances_user_status", "workflow_instances", ["user_id", "status"]
    )
    op.create_index(
        "ix_workflow_instances_correlation_id", "workflow_instances", ["correlation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_instances_correlation_id", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_user_status", table_name="workflow_instances")
    op.drop_table("workflow_instances")
