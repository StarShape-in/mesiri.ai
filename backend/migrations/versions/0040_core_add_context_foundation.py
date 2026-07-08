"""M4 context foundation — authoritative tenant/identity/authorization schema.

Adds the tables the Context Foundation resolves against. Kept separate from the
control-plane ``organizations`` / ``users`` tables (which model SaaS
provisioning) so M4 owns a clean, tenant-scoped authorization model. String
primary keys follow the repo's prefixed-id convention (e.g. ``proj_...``).

Revision ID: 0040
Revises: 0030
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "context_users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_subject", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("context_users.id"), nullable=False),
        sa.UniqueConstraint("provider", "external_subject", name="uq_external_identity"),
    )
    op.create_index("ix_external_identities_user", "external_identities", ["user_id"])

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("context_organizations.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("context_users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership"),
    )
    op.create_index("ix_memberships_user", "organization_memberships", ["user_id"])
    op.create_index("ix_memberships_org", "organization_memberships", ["organization_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("context_organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "membership_roles",
        sa.Column("membership_id", sa.String(), sa.ForeignKey("organization_memberships.id"), primary_key=True),
        sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id"), primary_key=True),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.String(), sa.ForeignKey("permissions.id"), primary_key=True),
    )

    op.create_table(
        "context_projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("context_organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_context_projects_org", "context_projects", ["organization_id"])
    op.create_index("ix_context_projects_org_name", "context_projects", ["organization_id", "name"])

    op.create_table(
        "context_sites",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("context_projects.id"), nullable=False),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("context_organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_context_sites_project", "context_sites", ["project_id"])
    op.create_index("ix_context_sites_org_name", "context_sites", ["organization_id", "name"])

    op.create_table(
        "project_memberships",
        sa.Column("user_id", sa.String(), sa.ForeignKey("context_users.id"), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("context_projects.id"), primary_key=True),
    )
    op.create_table(
        "site_memberships",
        sa.Column("user_id", sa.String(), sa.ForeignKey("context_users.id"), primary_key=True),
        sa.Column("site_id", sa.String(), sa.ForeignKey("context_sites.id"), primary_key=True),
    )

    op.create_table(
        "user_context_preferences",
        sa.Column("organization_id", sa.String(), sa.ForeignKey("context_organizations.id"), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("context_users.id"), primary_key=True),
        sa.Column("default_project_id", sa.String(), sa.ForeignKey("context_projects.id"), nullable=True),
        sa.Column("default_site_id", sa.String(), sa.ForeignKey("context_sites.id"), nullable=True),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "user_context_preferences",
        "site_memberships",
        "project_memberships",
        "context_sites",
        "context_projects",
        "role_permissions",
        "membership_roles",
        "permissions",
        "roles",
        "organization_memberships",
        "external_identities",
        "context_users",
        "context_organizations",
    ):
        op.drop_table(table)
