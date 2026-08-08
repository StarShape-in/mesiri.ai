"""Add automations -- user-defined recurring schedules that queue #9
Notifications rows.

A user says "every day at 5pm send me the DPR" or "at 3pm tell me who
hasn't reported" -- this table is the durable rule that statement becomes.
The scheduler (apps/whatsapp-assistant/src/runtime/automation_runner.py)
polls for rows whose local wall-clock time has passed `time_of_day` and
`last_run_on` is not today, resolves the audience, and claims one row per
recipient in the EXISTING `notifications` queue (migration 0453) under
`rule_key = 'automation:' || id` -- this table deliberately owns no send
state or dedup logic of its own; `notifications.occurred_on` is still the
single at-most-once guarantee, `automations.last_run_on` only avoids
re-evaluating an already-fired automation on every tick.

`audience` is a discriminator, not a foreign key, because the four
audiences are shaped completely differently (nobody vs an explicit id list
vs a role vs "whoever hasn't reported") -- same reasoning as
`daily_reports.level` (migration 0440) using a plain column rather than
forcing every audience through one shape:
  - SELF: no extra column needed -- the recipient is `created_by`.
  - USERS: `audience_user_ids` (JSONB array of user id strings).
  - ROLE: `audience_role` (e.g. "SITE_ENGINEER").
  - NON_REPORTERS: computed at run time from the reporting-compliance query,
    scoped to `project_id`/`site_id`; no stored column.

Revision ID: 0455
Revises: 0454
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0455"
down_revision = "0454"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "automations" in inspector.get_table_names():
        return

    op.create_table(
        "automations",
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
        sa.Column(
            "site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
        ),
        # "SEND_DPR" | "COMPLIANCE_SUMMARY" | "REMINDER" -- a plain string,
        # not a DB enum, same reasoning as notifications.rule_key (migration
        # 0453): the action set is expected to grow and a DB enum migration
        # per new action is friction for no real benefit here.
        sa.Column("action", sa.String(), nullable=False),
        # "SELF" | "USERS" | "ROLE" | "NON_REPORTERS"
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("audience_user_ids", JSONB, nullable=True),
        sa.Column("audience_role", sa.String(), nullable=True),
        # REMINDER's free text. Unused by SEND_DPR/COMPLIANCE_SUMMARY, which
        # render their own message from live data.
        sa.Column("message", sa.Text(), nullable=True),
        # "DAILY" | "WEEKDAYS" | "WEEKLY"
        sa.Column("frequency", sa.String(), nullable=False, server_default="DAILY"),
        # 0=Monday .. 6=Sunday, WEEKLY only.
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("time_of_day", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        # The last LOCAL date this automation actually fired -- the
        # runner's cheap "already handled today, don't re-evaluate" guard.
        # Not the at-most-once guarantee itself (notifications.occurred_on
        # is), so a race between two runner ticks is harmless: both would
        # attempt the same notifications claim and the loser's ON CONFLICT
        # DO NOTHING makes it a no-op, not a duplicate send.
        sa.Column("last_run_on", sa.Date(), nullable=True),
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
    )
    op.create_index(
        "ix_automations_due_scan",
        "automations",
        ["organization_id", "enabled"],
        postgresql_where=sa.text("enabled = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_automations_due_scan", table_name="automations")
    op.drop_table("automations")
