"""Add UNIQUE(source_type, source_id, transaction_type) to money_transactions.

Mirrors 0310's `uq_material_movements_source` guard on material_movements.
Every current writer of money_transactions (PostgresExpensePaymentRepository's
record_payment/reverse_payment, via RecordExpenseHandler) already sits behind
an outer idempotency_keys claim or a payment-status transition, so this is
not closing an exploitable gap today -- it is forward-looking defense for
Finance Module Slices 3/5/7 (transfers, petty cash, reversal), which will
add more writers to this same ledger table and must not be able to double-
post a retried confirm.

No existing duplicate rows are expected (money_transactions is currently
written only through the single expense_payment path this migration follows
directly), but the upgrade is written to fail loudly rather than silently
constrain over duplicates if that assumption is ever wrong.

Revision ID: 0367
Revises: 0366
Create Date: 2026-07-25
"""

from __future__ import annotations

from alembic import op

revision = "0367"
down_revision = "0366"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_money_transactions_source",
        "money_transactions",
        ["source_type", "source_id", "transaction_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_money_transactions_source", "money_transactions", type_="unique")
