"""Add organization_settings — per-tenant configuration key/value store.

Every permission rule in the codebase is currently hardcoded in Python
(authorization/service.py's _ORG_WIDE_ROLES, materials/validation.py's
ADJUSTMENT_ROLES, the literal role.upper() != "ADMIN" checks scattered
through domains/projects/router.py). That works for rules that are the same
for every client, but not for anything a client is supposed to be able to
tune for themselves from the control panel.

Deliberately generic key/jsonb rather than one column per setting: the first
consumer is whatsapp_material_create_roles (which roles may add a material
to the catalog straight from a WhatsApp report -- see STA-139), but the
whole point is that the next per-client toggle needs a row, not a migration.
Readers are responsible for their own default when no row exists, so an
org that has never touched its settings behaves exactly as it did before
this table existed.

ON DELETE CASCADE from organizations, matching the tenant-deletion contract
0361 established for every org-scoped table.

Revision ID: 0365
Revises: 0364
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0365"
down_revision = "0364"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
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
        sa.Column("updated_by", sa.UUID(as_uuid=True), nullable=True),
        # One row per (org, key) -- the read path assumes at most one match
        # and the write path upserts on this constraint.
        sa.UniqueConstraint("organization_id", "key", name="uq_organization_settings_org_key"),
    )
    op.create_index(
        "ix_organization_settings_organization_id",
        "organization_settings",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_organization_settings_organization_id", table_name="organization_settings")
    op.drop_table("organization_settings")
