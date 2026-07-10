"""M6.5 pt.2 — enforce identity bridges and restore workflow_instances UUID FKs.

Runs after backfill/reconcile. Fails if bridge columns are NULL or workflow_instances
rows cannot be mapped to canonical UUIDs.

Revision ID: 0195
Revises: 0190
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0195"
down_revision = "0190"
branch_labels = None
depends_on = None

_BRIDGE_CHECKS = (
    ("context_organizations", "canonical_organization_id"),
    ("context_users", "canonical_user_id"),
    ("context_projects", "canonical_project_id"),
    ("context_sites", "canonical_site_id"),
)


def _assert_no_null_bridges() -> None:
    conn = op.get_bind()
    for table, column in _BRIDGE_CHECKS:
        count = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
        ).scalar_one()
        if count:
            raise RuntimeError(
                f"M6.5 backfill incomplete: {count} row(s) in {table} have NULL {column}. "
                "Run scripts/backfill_identity_bridge.py before upgrading to 0195."
            )


def _restore_workflow_instance_uuid_columns() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "workflow_instances" not in inspector.get_table_names():
        return

    cols = {c["name"]: c for c in inspector.get_columns("workflow_instances")}
    org_col = cols.get("organization_id")
    if org_col is None:
        return

    # Already UUID (e.g. 0130 applied but 0170 never ran).
    if isinstance(org_col["type"], sa.UUID):
        return

    # Map string context IDs to canonical UUIDs where possible.
    conn.execute(
        sa.text(
            """
            UPDATE workflow_instances wi
            SET organization_id = co.canonical_organization_id::text
            FROM context_organizations co
            WHERE wi.organization_id = co.id
              AND co.canonical_organization_id IS NOT NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE workflow_instances wi
            SET user_id = cu.canonical_user_id::text
            FROM context_users cu
            WHERE wi.user_id = cu.id
              AND cu.canonical_user_id IS NOT NULL
            """
        )
    )

    unmappable = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM workflow_instances
            WHERE organization_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
               OR user_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            """
        )
    ).scalar_one()
    if unmappable:
        raise RuntimeError(
            f"{unmappable} workflow_instances row(s) cannot be converted to canonical UUIDs. "
            "Fix mappings before upgrading to 0195."
        )

    op.alter_column(
        "workflow_instances",
        "organization_id",
        type_=sa.UUID(as_uuid=True),
        postgresql_using="organization_id::uuid",
    )
    op.alter_column(
        "workflow_instances",
        "user_id",
        type_=sa.UUID(as_uuid=True),
        postgresql_using="user_id::uuid",
    )
    op.create_foreign_key(
        "workflow_instances_organization_id_fkey",
        "workflow_instances",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_foreign_key(
        "workflow_instances_user_id_fkey",
        "workflow_instances",
        "users",
        ["user_id"],
        ["id"],
    )


def upgrade() -> None:
    _assert_no_null_bridges()
    _restore_workflow_instance_uuid_columns()

    for table, column in _BRIDGE_CHECKS:
        op.alter_column(table, column, nullable=False)


def downgrade() -> None:
    for table, column in reversed(_BRIDGE_CHECKS):
        op.alter_column(table, column, nullable=True)

    inspector = sa.inspect(op.get_bind())
    if "workflow_instances" not in inspector.get_table_names():
        return

    op.drop_constraint("workflow_instances_user_id_fkey", "workflow_instances", type_="foreignkey")
    op.drop_constraint(
        "workflow_instances_organization_id_fkey", "workflow_instances", type_="foreignkey"
    )
    op.alter_column(
        "workflow_instances",
        "user_id",
        type_=sa.String(),
        postgresql_using="user_id::text",
    )
    op.alter_column(
        "workflow_instances",
        "organization_id",
        type_=sa.String(),
        postgresql_using="organization_id::text",
    )
