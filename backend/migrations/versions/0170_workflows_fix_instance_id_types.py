"""Fix workflow_instances.organization_id/user_id to match the M4 id space.

workflow_instances (migration 0130) originally FK'd organization_id/
user_id as UUID to the control-plane organizations/users tables. But
ContextResolver — the actual producer of these ids on ResolvedContext /
CanonicalEvent / PlannerDecision / WorkflowState — resolves against
context_organizations/context_users, which use arbitrary string ids (e.g.
"org_a"), not UUIDs. Inserting a real resolved id into the old UUID column
would fail on every workflow start. Converts both columns to plain String,
matching every other M4-consuming contract (no FK — same as those contracts,
which carry ids without enforced referential integrity at this layer).

Revision ID: 0170
Revises: 0160
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0170"
down_revision = "0160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "workflow_instances_organization_id_fkey", "workflow_instances", type_="foreignkey"
    )
    op.drop_constraint("workflow_instances_user_id_fkey", "workflow_instances", type_="foreignkey")
    op.alter_column(
        "workflow_instances",
        "organization_id",
        type_=sa.String(),
        postgresql_using="organization_id::text",
    )
    op.alter_column(
        "workflow_instances",
        "user_id",
        type_=sa.String(),
        postgresql_using="user_id::text",
    )


def downgrade() -> None:
    op.alter_column(
        "workflow_instances",
        "user_id",
        type_=sa.UUID(as_uuid=True),
        postgresql_using="user_id::uuid",
    )
    op.alter_column(
        "workflow_instances",
        "organization_id",
        type_=sa.UUID(as_uuid=True),
        postgresql_using="organization_id::uuid",
    )
    op.create_foreign_key(
        "workflow_instances_user_id_fkey", "workflow_instances", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "workflow_instances_organization_id_fkey",
        "workflow_instances",
        "organizations",
        ["organization_id"],
        ["id"],
    )
