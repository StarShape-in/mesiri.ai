"""company details and whatsapp mapping columns

Revision ID: 0280
Revises: 0270
Create Date: 2026-07-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0280"
down_revision = "0270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add columns to organizations table ---
    op.add_column("organizations", sa.Column("code", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("email", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("address", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("primary_contact", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("timezone", sa.String(), server_default="UTC", nullable=False))
    
    op.create_index("ix_organizations_code", "organizations", ["code"], unique=True)

    # --- Add columns to inbound_messages table ---
    op.add_column("inbound_messages", sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("inbound_messages", sa.Column("project_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("inbound_messages", sa.Column("site_id", sa.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key("fk_inbound_messages_organization_id", "inbound_messages", "organizations", ["organization_id"], ["id"])
    op.create_foreign_key("fk_inbound_messages_project_id", "inbound_messages", "projects", ["project_id"], ["id"])
    op.create_foreign_key("fk_inbound_messages_site_id", "inbound_messages", "sites", ["site_id"], ["id"])

    op.create_index("ix_inbound_messages_organization_id", "inbound_messages", ["organization_id"])
    op.create_index("ix_inbound_messages_project_id", "inbound_messages", ["project_id"])
    op.create_index("ix_inbound_messages_site_id", "inbound_messages", ["site_id"])


def downgrade() -> None:
    # --- Drop inbound_messages indices & columns ---
    op.drop_index("ix_inbound_messages_site_id", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_project_id", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_organization_id", table_name="inbound_messages")

    op.drop_constraint("fk_inbound_messages_site_id", "inbound_messages", type_="foreignkey")
    op.drop_constraint("fk_inbound_messages_project_id", "inbound_messages", type_="foreignkey")
    op.drop_constraint("fk_inbound_messages_organization_id", "inbound_messages", type_="foreignkey")

    op.drop_column("inbound_messages", "site_id")
    op.drop_column("inbound_messages", "project_id")
    op.drop_column("inbound_messages", "organization_id")

    # --- Drop organizations indices & columns ---
    op.drop_index("ix_organizations_code", table_name="organizations")

    op.drop_column("organizations", "timezone")
    op.drop_column("organizations", "primary_contact")
    op.drop_column("organizations", "address")
    op.drop_column("organizations", "phone")
    op.drop_column("organizations", "email")
    op.drop_column("organizations", "code")
