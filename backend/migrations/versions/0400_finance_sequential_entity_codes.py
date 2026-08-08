"""Add and backfill sequential codes for money_accounts, vendors, and expense_categories.

Adds nullable 'code' column to money_accounts and vendors tables.
Backfills money_accounts (ACC-001), vendors (VND-001), and expense_categories (CAT-001)
sequentially per organization.

Revision ID: 0400
Revises: 0390
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0400"
down_revision = "0390"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add code column to money_accounts
    op.add_column("money_accounts", sa.Column("code", sa.String(), nullable=True))

    # 2. Add code column to vendors
    op.add_column("vendors", sa.Column("code", sa.String(), nullable=True))

    # 3. Backfill money_accounts code (ACC-001, ACC-002, ...)
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, 'ACC-' || LPAD(ROW_NUMBER() OVER (PARTITION BY organization_id ORDER BY created_at ASC, id ASC)::text, 3, '0') AS new_code
                FROM money_accounts
            )
            UPDATE money_accounts m
            SET code = r.new_code
            FROM ranked r
            WHERE m.id = r.id AND (m.code IS NULL OR m.code NOT LIKE 'ACC-%');
            """
        )
    )

    # 4. Backfill vendors code (VND-001, VND-002, ...)
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, 'VND-' || LPAD(ROW_NUMBER() OVER (PARTITION BY organization_id ORDER BY created_at ASC, id ASC)::text, 3, '0') AS new_code
                FROM vendors
            )
            UPDATE vendors v
            SET code = r.new_code
            FROM ranked r
            WHERE v.id = r.id AND (v.code IS NULL OR v.code NOT LIKE 'VND-%');
            """
        )
    )

    # 5. Backfill expense_categories code (CAT-001, CAT-002, ...)
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, 'CAT-' || LPAD(ROW_NUMBER() OVER (PARTITION BY organization_id ORDER BY created_at ASC, id ASC)::text, 3, '0') AS new_code
                FROM expense_categories
            )
            UPDATE expense_categories c
            SET code = r.new_code
            FROM ranked r
            WHERE c.id = r.id AND (c.code IS NULL OR c.code NOT LIKE 'CAT-%');
            """
        )
    )


def downgrade() -> None:
    op.drop_column("vendors", "code")
    op.drop_column("money_accounts", "code")
