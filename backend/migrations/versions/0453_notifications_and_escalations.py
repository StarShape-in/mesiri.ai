"""Add notifications and escalations (#9 Notifications, #10 Human Review).

Two tables, two different durability guarantees:

`notifications` is a QUEUE with an at-most-once guarantee enforced at the
schema level, not just in application code -- UNIQUE(organization_id,
rule_key, subject_id, occurred_on) means a scheduled check that runs twice
in one day (overlapping cron, a retried script) physically cannot queue the
same notification twice. This is the single most important property a
notification system has: a site manager woken up twice by the same "missing
DPR" nudge stops trusting the product. `occurred_on` (a date, not a
timestamp) is the day the notification is FOR, not when it was queued --
this is what the unique constraint actually keys on.

`escalations` is a durable REVIEW RECORD, not a re-triggerable draft. An
escalation is created when the AI has nothing usable to act on at all
(#7 Low-Confidence Routing's ESCALATE outcome -- see planner/ambiguity.py) --
there is no draft_action to "approve into execution" in that case, only a
snapshot of what came in and why it couldn't be handled. Resolving one is a
human decision recorded with a free-text note, not an automated replay.

Revision ID: 0453
Revises: 0452
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0453"
down_revision = "0452"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "notifications" not in existing_tables:
        _create_notifications_table()
    if "escalations" not in existing_tables:
        _create_escalations_table()


def _create_notifications_table() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True),
        # "missing_dpr" | "no_updates_today" | "stuck_confirmation" |
        # "unresolved_issue" -- see application/notifications/checks.py.
        # A plain string, not an enum: new checks are added by extending
        # that module, and a DB enum migration for every new check name
        # would be friction for no real benefit (nothing else constrains
        # this column's values at the schema level).
        sa.Column("rule_key", sa.String(), nullable=False),
        # What the notification is ABOUT -- a workflow_instance_id for
        # "stuck_confirmation", a site_id (as text) for "no_updates_today",
        # a daily_reports absence has no natural id so it reuses site_id.
        # Free-form on purpose: each rule_key defines its own meaning.
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "recipient_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "organization_id", "rule_key", "subject_id", "occurred_on", name="uq_notifications_dedup"
        ),
    )
    op.create_index(
        "ix_notifications_pending", "notifications", ["status", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def _create_escalations_table() -> None:
    op.create_table(
        "escalations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        # A frozen snapshot of what came in and why it couldn't be handled --
        # never a live reference to a workflow_instance (that row may not
        # even exist yet at ESCALATE time -- see planner/ambiguity.py's
        # UNUSABLE case, which fires before any workflow starts).
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "assigned_to_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "resolved_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_escalations_pending", "escalations", ["organization_id", "status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_escalations_pending", table_name="escalations")
    op.drop_table("escalations")

    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_table("notifications")
