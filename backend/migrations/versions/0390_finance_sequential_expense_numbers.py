"""Backfill and enforce sequential expense numbers per organization and project.

Backfills existing NULL or unformatted expense_number values with
EXP-001, EXP-002, ... sequentially per (organization_id, project_id).

Revision ID: 0390
Revises: 0380
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0390"
down_revision = "0380"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Backfill expense_number for all existing rows per (organization_id, project_id)
    # ordered by occurred_date, created_at, id
    conn.execute(
        sa.text(
            """
            WITH ranked_expenses AS (
                SELECT
                    id,
                    'EXP-' || LPAD(
                        ROW_NUMBER() OVER (
                            PARTITION BY organization_id, project_id
                            ORDER BY occurred_date ASC, created_at ASC, id ASC
                        )::text,
                        3,
                        '0'
                    ) AS new_num
                FROM expenses
            )
            UPDATE expenses e
            SET expense_number = re.new_num
            FROM ranked_expenses re
            WHERE e.id = re.id
              AND (e.expense_number IS NULL OR e.expense_number NOT LIKE 'EXP-%');
            """
        )
    )


def downgrade() -> None:
    pass
