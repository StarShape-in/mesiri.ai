"""Add inbound_messages.reply_wamid -- resolves a reply to Mesiri's own message (#11 Reply Workflow).

`inbound_messages.dedup_key` already lets PostgresReplyContextProvider
(context/postgres_repositories.py) resolve a reply to the SENDER's own
earlier message. It cannot resolve a reply to MESIRI's own outbound message
(e.g. replying to "✅ Recorded." to reference or correct that record later)
because the outbound message's WhatsApp id (wamid) was never captured
anywhere. This column is that capture point: the wamid of the reply Mesiri
sent for this inbound message, set once the send completes (see
runtime/inbound_journey.py's final "Send reply" step and
channel/whatsapp/outbound.py's send_text_capturing_id).

Scope, stated plainly: this pass only captures the wamid for a PLAIN TEXT
reply (the send_text branch of runtime/reply_dispatch.py's send_reply_spec).
Replies rendered as an interactive list/button message are not yet
id-capturing -- extending send_list/send_button the same way is a
mechanical follow-up, not a design gap.

Revision ID: 0452
Revises: 0450
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0452"
down_revision = "0450"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("inbound_messages")}
    if "reply_wamid" not in columns:
        op.add_column("inbound_messages", sa.Column("reply_wamid", sa.String(), nullable=True))
        op.create_index(
            "ix_inbound_messages_reply_wamid", "inbound_messages", ["reply_wamid"],
            postgresql_where=sa.text("reply_wamid IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("ix_inbound_messages_reply_wamid", table_name="inbound_messages")
    op.drop_column("inbound_messages", "reply_wamid")
