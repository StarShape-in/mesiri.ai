"""M6.5 pt.1 — nullable canonical bridge columns on context entity tables.

Adds canonical_*_id FK columns linking context_* projections to control-plane
UUID entities. Schema only — no backfill dependency, no workflow_instances changes.

Revision ID: 0190
Revises: 0180
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0190"
down_revision = "0180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column, fk_target in (
        ("context_organizations", "canonical_organization_id", "organizations.id"),
        ("context_users", "canonical_user_id", "users.id"),
        ("context_projects", "canonical_project_id", "projects.id"),
        ("context_sites", "canonical_site_id", "sites.id"),
    ):
        op.add_column(
            table,
            sa.Column(column, sa.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_{column}",
            table,
            fk_target.split(".")[0],
            [column],
            [fk_target.split(".")[1]],
            ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_{column}", table, [column], unique=True)


def downgrade() -> None:
    for table, column in (
        ("context_sites", "canonical_site_id"),
        ("context_projects", "canonical_project_id"),
        ("context_users", "canonical_user_id"),
        ("context_organizations", "canonical_organization_id"),
    ):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_column(table, column)
