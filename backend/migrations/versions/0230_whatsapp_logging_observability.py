"""WhatsApp logging/observability upgrade.

Adds the columns and table needed to stop silently dropping data the control
panel's logs viewer can't show today:
- severity/event_source on journey_traces, so stage rows, provider-call rows,
  and unhandled-exception rows are distinguishable and filterable.
- provider_executions: first-class, queryable rows for "which LLM/provider
  handled this message" (previously only buried in journey_traces.stage_payload,
  which the read path deliberately excludes).
- raw_payload_captured / acknowledged_at / acknowledged_by / retry_of_id on
  inbound_messages, needed for the retry/acknowledge admin actions.

Revision ID: 0230
Revises: 0220
Create Date: 2026-07-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0230"
down_revision = "0220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- journey_traces: severity + event_source ---
    op.add_column(
        "journey_traces",
        sa.Column("severity", sa.String(), server_default="info", nullable=False),
    )
    op.add_column(
        "journey_traces",
        sa.Column("event_source", sa.String(), server_default="pipeline_stage", nullable=False),
    )

    # --- provider_executions ---
    op.create_table(
        "provider_executions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_provider_executions_correlation_id", "provider_executions", ["correlation_id"])
    op.create_index("ix_provider_executions_provider", "provider_executions", ["provider"])
    op.create_index("ix_provider_executions_created_at", "provider_executions", ["created_at"])

    # --- inbound_messages: retry/acknowledge/reply support ---
    op.add_column(
        "inbound_messages",
        sa.Column("raw_payload_captured", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("inbound_messages", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("inbound_messages", sa.Column("acknowledged_by", sa.String(), nullable=True))
    op.add_column("inbound_messages", sa.Column("retry_of_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("inbound_messages", sa.Column("assistant_reply", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("inbound_messages", "assistant_reply")
    op.drop_column("inbound_messages", "retry_of_id")
    op.drop_column("inbound_messages", "acknowledged_by")
    op.drop_column("inbound_messages", "acknowledged_at")
    op.drop_column("inbound_messages", "raw_payload_captured")

    op.drop_index("ix_provider_executions_created_at", table_name="provider_executions")
    op.drop_index("ix_provider_executions_provider", table_name="provider_executions")
    op.drop_index("ix_provider_executions_correlation_id", table_name="provider_executions")
    op.drop_table("provider_executions")

    op.drop_column("journey_traces", "event_source")
    op.drop_column("journey_traces", "severity")
