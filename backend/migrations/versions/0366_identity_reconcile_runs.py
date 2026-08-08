"""Add identity_reconcile_runs — an audit trail for the context-sync watchdog.

A user's project/site assignment is projected from the control plane into the
context layer (context_users / project_memberships / etc) on every write, but
that projection is deliberately best-effort: context/projection_hooks.py
catches and logs any failure so a projection error can't fail the dashboard
request that caused it. The cost of that choice is silent drift -- the
assistant keeps resolving the user against stale assignments, and nobody
finds out until someone manually runs scripts/backfill_identity_bridge.py.

`reconcile_all()` already repairs drift and is idempotent; what was missing
was anything running it on its own, and any record of whether it worked.
This table is the second half: auto-repair alone would still fail silently
if the reconcile itself started failing.

`duration_ms` is recorded deliberately. reconcile_all() re-projects every
organization/user/project/site/membership in one transaction, so its cost
grows with tenant count -- the run history is what makes that trend visible
early enough to move to an incremental strategy before it starts hurting.

Revision ID: 0366
Revises: 0365
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0366"
down_revision = "0365"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_reconcile_runs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        # "succeeded" | "completed_with_errors" | "failed"
        # A run that finished but repaired nothing is still "succeeded" --
        # no drift is the expected steady state, not a non-event.
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        # Per-entity counts from ReconcileReport, kept as a single jsonb blob
        # rather than one column each so adding an entity type to the
        # projection service doesn't need a migration here too.
        sa.Column("counts", postgresql.JSONB(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Truncated list of error strings -- enough to diagnose without
        # letting one pathological run write an unbounded row.
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        # "scheduled" (the background watchdog) or "manual" (admin-triggered),
        # so an operator can tell an automatic run from one they kicked off.
        sa.Column("trigger", sa.String(), nullable=False, server_default=sa.text("'scheduled'")),
    )
    # The read path is always "most recent runs first".
    op.create_index(
        "ix_identity_reconcile_runs_started_at",
        "identity_reconcile_runs",
        [sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identity_reconcile_runs_started_at", table_name="identity_reconcile_runs"
    )
    op.drop_table("identity_reconcile_runs")
