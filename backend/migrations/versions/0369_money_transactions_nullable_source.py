"""Make source_type and source_id nullable on money_transactions.

0080 created finance_account_transactions with `source_type` and `source_id` as NOT NULL
because every transaction in 0080 was tied to an expense or fuel refill.
0340 renamed finance_account_transactions to money_transactions and expanded transaction_type
to include `transfer`, `fund_received`, `adjustment`, etc. Transfers between accounts and general
money movements do not require an external source_type/source_id document.

Revision ID: 0369
Revises: 0368
Create Date: 2026-07-25
"""

from __future__ import annotations

from alembic import op

revision = "0369"
down_revision = "0368"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("money_transactions", "source_type", nullable=True)
    op.alter_column("money_transactions", "source_id", nullable=True)


def downgrade() -> None:
    op.alter_column("money_transactions", "source_type", nullable=False)
    op.alter_column("money_transactions", "source_id", nullable=False)
