"""Attendance-line fields a real Indian muster roll actually carries.

Until now a line held who worked, at what trade, how many, for what wage, and
optionally an activity -- which is everything a *typed WhatsApp message* says.
A photographed muster roll says more, and the three columns added here are the
ones that change what a day means rather than merely annotating it:

**attendance_status** -- a muster roll marks P / A / H per person per day.
Every line recorded so far has been assumed present, because a typed message
only ever names people who worked. A photographed sheet lists the whole crew
including the absentees, so without this column reading one sheet would invent
a day's work (and a day's wage) for everyone who did not turn up. Defaults to
'present', which is exactly right for every row already stored and for every
typed report that will follow.

**overtime_hours** -- OT is a separate column on the sheet and is paid at a
different rate. Captured now rather than folded into the wage, because a
number that has silently absorbed overtime cannot be taken apart again later.
Nothing computes OT pay yet; the rate rules vary by contractor and are not
being guessed at (principle: if it cannot be derived from what was recorded,
it is not produced).

**remarks** -- the free-text column at the right-hand edge of every sheet
("left early", "site closed 2pm"). Worth keeping verbatim: it is often the
only explanation of why a day looks unusual, and it costs nothing to store.

All three are nullable or defaulted, so existing rows stay valid and no
backfill is required. `headcount` deliberately stays INTEGER -- it is a count
of people, and half-days are expressed by attendance_status rather than by
making the count fractional (the day-fraction is applied when aggregating,
see repositories/workforce.py).

Revision ID: 0456
Revises: 0455
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0456"
down_revision = "0455"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "labour_attendance_lines",
        sa.Column(
            "attendance_status",
            sa.String(),
            nullable=False,
            server_default="present",
        ),
    )
    op.create_check_constraint(
        "ck_labour_attendance_lines_attendance_status",
        "labour_attendance_lines",
        "attendance_status IN ('present', 'absent', 'half_day')",
    )
    op.add_column(
        "labour_attendance_lines",
        sa.Column("overtime_hours", sa.Numeric(6, 2), nullable=True),
    )
    op.create_check_constraint(
        "ck_labour_attendance_lines_overtime_non_negative",
        "labour_attendance_lines",
        "overtime_hours IS NULL OR overtime_hours >= 0",
    )
    op.add_column(
        "labour_attendance_lines",
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    # Absent lines are excluded from every total, so the reports filter on this
    # column on every aggregation. Cheap index, and the column is low
    # cardinality precisely where a partial index helps.
    op.create_index(
        "ix_labour_attendance_lines_attendance_status",
        "labour_attendance_lines",
        ["attendance_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_labour_attendance_lines_attendance_status", "labour_attendance_lines")
    op.drop_constraint(
        "ck_labour_attendance_lines_overtime_non_negative", "labour_attendance_lines"
    )
    op.drop_constraint(
        "ck_labour_attendance_lines_attendance_status", "labour_attendance_lines"
    )
    op.drop_column("labour_attendance_lines", "remarks")
    op.drop_column("labour_attendance_lines", "overtime_hours")
    op.drop_column("labour_attendance_lines", "attendance_status")
