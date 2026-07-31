"""Allow 'CANCELLED' as a site issue status.

Until now a Site Issue could only ever move forward: OPEN -> ACKNOWLEDGED ->
RESOLVED/WONT_FIX. There was no way to say "I reported that by mistake" --
a blocker filed against the wrong site stayed on the register permanently,
counted against that site in every report, and the only escape was to
RESOLVE it, which is a lie: nothing was fixed because nothing was broken.

CANCELLED is deliberately a distinct terminal state rather than a reuse of
WONT_FIX. "We chose not to fix this" and "this was never a real issue" are
different facts about the site, and a DPR that folds the second into the
first overstates how many genuine blockers the site had. It is also NOT a
row delete (P1: records are transitioned, never destroyed) -- the mistaken
report stays auditable, it just stops counting as an open problem.

Enum-only change: no new column, no data movement, existing rows unaffected.
Safe inside Alembic's transaction on PG 12+ because the new value is added
but never *used* in this same transaction (PG 16 in CI and compose).

Revision ID: 0460
Revises: 0459
"""

from __future__ import annotations

from alembic import op

revision = "0460"
down_revision = "0459"
branch_labels = None
depends_on = None

_ENUM = "site_issue_status"
_PRIOR_VALUES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "WONT_FIX")


def upgrade() -> None:
    # IF NOT EXISTS so a re-run (or a database already carrying the value
    # from a hand-applied hotfix) is a no-op rather than a hard failure --
    # same defensive posture as 0430's _create_enum_if_not_exists.
    op.execute(f"ALTER TYPE {_ENUM} ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # Postgres cannot drop a value from an enum, so the type is rebuilt.
    # Any issue already cancelled is folded into WONT_FIX first: the
    # distinction above is lost, but the row and its history are not, and
    # WONT_FIX is the only prior value that is also terminal and also not a
    # claim that work happened.
    op.execute("ALTER TABLE site_issues ALTER COLUMN status DROP DEFAULT")
    op.execute(f"ALTER TYPE {_ENUM} RENAME TO {_ENUM}_old")
    values = ", ".join(f"'{v}'" for v in _PRIOR_VALUES)
    op.execute(f"CREATE TYPE {_ENUM} AS ENUM ({values})")
    # Runs while the column is still the *old* type, which still accepts
    # both CANCELLED and WONT_FIX -- so this must come before the cast.
    op.execute("UPDATE site_issues SET status = 'WONT_FIX' WHERE status = 'CANCELLED'")
    op.execute(
        f"ALTER TABLE site_issues ALTER COLUMN status TYPE {_ENUM} "
        f"USING status::text::{_ENUM}"
    )
    op.execute("ALTER TABLE site_issues ALTER COLUMN status SET DEFAULT 'OPEN'")
    op.execute(f"DROP TYPE {_ENUM}_old")
