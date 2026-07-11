"""Add projects reporting configuration and project members table.

Revision ID: 0260
Revises: 0250
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0260"
down_revision = "0250"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to projects table
    op.add_column(
        "projects",
        sa.Column("reporting_timezone", sa.String(), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "projects",
        sa.Column("reporting_cutoff_time", sa.String(), nullable=False, server_default="18:00"),
    )
    op.add_column(
        "projects",
        sa.Column(
            "auto_generate_dpr", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "projects",
        sa.Column("required_report_types", JSONB, nullable=True),
    )

    # Create project_members table
    op.create_table(
        "project_members",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False, server_default="SITE_ENGINEER"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_table("project_members")

    op.drop_column("projects", "required_report_types")
    op.drop_column("projects", "auto_generate_dpr")
    op.drop_column("projects", "reporting_cutoff_time")
    op.drop_column("projects", "reporting_timezone")
