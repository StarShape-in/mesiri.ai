"""Add tax_rate, tax_amount, is_tax_inclusive to expenses.

Preserves optional receipt-extracted or user-entered tax metadata
without enforcing tax compliance or accounting calculations.

Revision ID: 0380
Revises: 0370
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0380"
down_revision = "0370"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("tax_rate", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column(
            "is_tax_inclusive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("expenses", "is_tax_inclusive")
    op.drop_column("expenses", "tax_amount")
    op.drop_column("expenses", "tax_rate")
