"""Add user status, access_policy, and sites table.

- users.status  — lifecycle state visible on the mobile User Details screen
- users.access_policy — JSONB project/site access policy saved from the mobile app
- sites          — org-scoped sites belonging to a project (feeds the site picker)

Revision ID: f7g8h9i0j1k2
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f7g8h9i0j1k2"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column("access_policy", JSONB, nullable=True),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="active",
        ),
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
    op.create_index("ix_sites_project_id", "sites", ["project_id"])
    op.create_index("ix_sites_organization_id", "sites", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_sites_organization_id", table_name="sites")
    op.drop_index("ix_sites_project_id", table_name="sites")
    op.drop_table("sites")
    op.drop_column("users", "access_policy")
    op.drop_column("users", "status")
