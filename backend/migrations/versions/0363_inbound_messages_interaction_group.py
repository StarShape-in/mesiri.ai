"""Add inbound_messages.interaction_group_id for multi-turn report grouping.

0362 only tagged the message that directly started or resumed a
workflow_instances row with a real workflow_instance_id FK. In practice a
material/expense report usually goes through several gate-clarification taps
first (ambiguous material picker, Stock Unit mismatch confirm, project
picker) before a workflow ever exists to link to -- those intermediate taps,
and the very first voice/text report itself, were left untagged, so the
control-panel logs viewer only ever bracketed the final "yes" confirmation
by itself.

interaction_group_id is a plain string (not an FK -- no workflow_instances
row may exist yet when it's written), set to
CanonicalEventV2.correlation_id, which survives every pop_pending/model_copy
across the gate chain unchanged and therefore always points back to the
originating report's own correlation_id. Once a workflow instance is
eventually created from that same event, workflow_instances.correlation_id
equals this same origin value (see workflows/runtime.py), so the read path
(message_logger.py) can resolve every gate-tap's row to the same workflow
via `LEFT JOIN workflow_instances ON workflow_instances.correlation_id =
inbound_messages.interaction_group_id`, with no further backfill needed.

Revision ID: 0363
Revises: 0362
Create Date: 2026-07-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0363"
down_revision = "0362"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inbound_messages",
        sa.Column("interaction_group_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_inbound_messages_interaction_group_id",
        "inbound_messages",
        ["interaction_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_messages_interaction_group_id", table_name="inbound_messages")
    op.drop_column("inbound_messages", "interaction_group_id")
