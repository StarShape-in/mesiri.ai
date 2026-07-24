"""Link inbound_messages to the workflow_instances they started/resumed.

Backs the control-panel logs viewer's workflow-interaction grouping: a voice
expense report and its later "YES" confirmation are separate inbound_messages
rows with distinct correlation_ids, and nothing on that table ties them
together today (see the message_logger.py / trace_logger.py module
docstrings for the existing correlation_id-only read paths). The only
existing linkage lives in workflow_instances (single-active-confirmation-
per-user invariant, see interactions/correlation.py), which the logs reader
never joins against.

workflow_instance_id is nullable and set best-effort by the pipeline
(runtime/inbound_journey.py, interactions/handler.py) whenever a message
starts or resumes a workflow -- most messages (greetings, whoami, direct
replies) never touch a workflow and stay NULL.

Revision ID: 0362
Revises: 0361
Create Date: 2026-07-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0362"
down_revision = "0361"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_messages",
        sa.Column("workflow_instance_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_inbound_messages_workflow_instance_id",
        "inbound_messages",
        "workflow_instances",
        ["workflow_instance_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_inbound_messages_workflow_instance_id",
        "inbound_messages",
        ["workflow_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_messages_workflow_instance_id", table_name="inbound_messages")
    op.drop_constraint(
        "fk_inbound_messages_workflow_instance_id", "inbound_messages", type_="foreignkey"
    )
    op.drop_column("inbound_messages", "workflow_instance_id")
