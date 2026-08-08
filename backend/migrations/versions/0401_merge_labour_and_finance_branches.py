"""Merge the labour-workforce and finance-sequential-codes branches.

Both branched independently off 0370 (0369 -> 0370 branchpoint): Labour
Module Phase 3 went 0370 -> 0371, while Finance went
0370 -> 0380 (tax fields) -> 0390 (sequential expense numbers) -> 0400
(sequential account/vendor/category codes). CI's `alembic upgrade head`
failed with "Multiple head revisions" once both landed on main -- this
merge revision converges them into one head without altering either
chain's already-applied migrations.

Revision ID: 0401
Revises: 0371, 0400
Create Date: 2026-07-26
"""

from __future__ import annotations

revision = "0401"
down_revision = ("0371", "0400")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
