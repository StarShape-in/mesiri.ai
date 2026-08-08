"""Allow 'attendance_team_photo' as a labour attachment type.

A photo of the crew who turned up is evidence of a different kind from a
photographed attendance sheet: the sheet is the *source* the record was read
from, the team photo is *corroboration* taken afterwards. Keeping them apart
by type is what lets a gallery, a daily report or a future verification step
ask for one without getting the other -- and it costs nothing now, whereas
separating them later would mean guessing from a mixed pile.

Constraint-only change: no new column, no data movement, and existing rows
are unaffected.

Revision ID: 0454
Revises: 0453
"""

from __future__ import annotations

from alembic import op

revision = "0454"
down_revision = "0453"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_labour_attendance_attachments_type"
_TABLE = "labour_attendance_attachments"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "attachment_type IN ('attendance_sheet', 'attendance_team_photo', 'other')",
    )


def downgrade() -> None:
    # Re-narrowing would fail against any team photo already stored, so those
    # are folded into 'other' first -- the type is lost, the evidence is not.
    op.execute(
        "UPDATE labour_attendance_attachments SET attachment_type = 'other' "
        "WHERE attachment_type = 'attendance_team_photo'"
    )
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "attachment_type IN ('attendance_sheet', 'other')",
    )
