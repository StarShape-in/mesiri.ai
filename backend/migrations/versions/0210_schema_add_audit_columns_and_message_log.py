"""Add audit timestamps + inbound_messages/journey_traces debug tables.

Fills the schema gaps found in the prod DB audit:
- G1: created_at on RBAC junction tables (roles, permissions, role_permissions,
  membership_roles, project_memberships, site_memberships)
- G2: created_at on external_identities
- G3: updated_at + trigger on context_* tables
- G4: inbound_messages table for raw WhatsApp message logging
- G5: journey_traces table for pipeline-stage trace logging

Revision ID: 0210
Revises: 0200
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0210"
down_revision = "0200"
branch_labels = None
depends_on = None

_RBAC_TABLES = (
    "roles",
    "permissions",
    "role_permissions",
    "membership_roles",
    "project_memberships",
    "site_memberships",
)

_CONTEXT_TABLES = (
    "context_organizations",
    "context_users",
    "context_projects",
    "context_sites",
)


def upgrade() -> None:
    # --- G1: created_at on RBAC junction tables ---
    for table in _RBAC_TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    # --- G2: created_at on external_identities ---
    op.add_column(
        "external_identities",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # --- G3: updated_at + trigger on context_* tables ---
    op.execute(
        "CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ "
        "BEGIN NEW.updated_at = now(); RETURN NEW; END; "
        "$$ LANGUAGE plpgsql;"
    )
    for table in _CONTEXT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )

    # --- G4: inbound_messages ---
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("sender_wa_id", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_message", sa.JSON(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("media_object_key", sa.String(), nullable=True),
        sa.Column("dedup_key", sa.String(), nullable=False, unique=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", sa.String(), server_default="pending", nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
    )
    op.create_index("ix_inbound_messages_correlation_id", "inbound_messages", ["correlation_id"])
    op.create_index("ix_inbound_messages_sender_wa_id", "inbound_messages", ["sender_wa_id"])
    op.create_index("ix_inbound_messages_received_at", "inbound_messages", ["received_at"])

    # --- G5: journey_traces ---
    op.create_table(
        "journey_traces",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("stage_payload", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_journey_traces_correlation_id", "journey_traces", ["correlation_id"])
    op.create_index(
        "ix_journey_traces_correlation_stage", "journey_traces", ["correlation_id", "stage"]
    )


def downgrade() -> None:
    # G5
    op.drop_index("ix_journey_traces_correlation_stage", table_name="journey_traces")
    op.drop_index("ix_journey_traces_correlation_id", table_name="journey_traces")
    op.drop_table("journey_traces")

    # G4
    op.drop_index("ix_inbound_messages_received_at", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_sender_wa_id", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_correlation_id", table_name="inbound_messages")
    op.drop_table("inbound_messages")

    # G3
    for table in _CONTEXT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated ON {table};")
        op.drop_column(table, "updated_at")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

    # G2
    op.drop_column("external_identities", "created_at")

    # G1
    for table in _RBAC_TABLES:
        op.drop_column(table, "created_at")
