"""Add projects.auto_dpr_last_run_on.

`projects.auto_generate_dpr`/`reporting_cutoff_time`/`reporting_timezone`
(migration 0260) have been dashboard-editable since they were added, but
nothing has ever read them -- toggling "auto-generate DPR" on has done
nothing. This column is the missing piece that makes the toggle real: the
per-local-day "already fired" guard the new scheduler step
(apps/whatsapp-assistant/src/runtime/project_auto_dpr.py) needs, mirroring
`automations.last_run_on` (migration 0455) exactly -- same reasoning,
same shape, one level up (a project's own standing schedule rather than a
user-owned automation row).

Revision ID: 0458
Revises: 0457
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0458"
down_revision = "0457"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("auto_dpr_last_run_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "auto_dpr_last_run_on")
