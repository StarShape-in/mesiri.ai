"""Add app projects table (control-plane, org-scoped).

The mobile app's Projects screen reads live, tenant-scoped project rows keyed to
the same control-plane ``organizations`` table the JWT ``org`` claim points at
(and that ``users`` are FK'd to). This is distinct from the M4 assistant-context
``context_projects`` table, which serves understanding/context resolution.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("client", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        # Health status: on_track | at_risk | critical.
        sa.Column("status", sa.String(), nullable=False, server_default="on_track"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")
