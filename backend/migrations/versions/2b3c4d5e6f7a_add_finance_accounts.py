"""Add finance_accounts and finance_account_transactions.

Bank/cash accounts, org-scoped. Balance is never mutated directly — it is
always `opening_balance + sum(finance_account_transactions for this account)`.
This is deliberately event-sourced (ledger, not a mutable column) so the future
Accounting module can build reconciliation and reporting on top without a
schema redesign. Expense (and Equipment fuel spend) reference an account and
each debit is recorded as a transaction row, never as a direct balance update.

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_accounts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Account type: bank | cash
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=True),
        sa.Column("account_number_last4", sa.String(), nullable=True),
        sa.Column("ifsc", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("opening_balance_date", sa.Date(), nullable=False),
        # Status: active | closed
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_finance_accounts_organization_id", "finance_accounts", ["organization_id"])

    op.create_table(
        "finance_account_transactions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("finance_accounts.id"),
            nullable=False,
        ),
        # Direction: debit | credit
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        # What triggered this movement, e.g. "expense", "fuel_refill"
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("occurred_time", sa.Time(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_finance_account_transactions_account_id",
        "finance_account_transactions",
        ["account_id"],
    )
    op.create_index(
        "ix_finance_account_transactions_source",
        "finance_account_transactions",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_finance_account_transactions_source", table_name="finance_account_transactions"
    )
    op.drop_index(
        "ix_finance_account_transactions_account_id", table_name="finance_account_transactions"
    )
    op.drop_table("finance_account_transactions")
    op.drop_index("ix_finance_accounts_organization_id", table_name="finance_accounts")
    op.drop_table("finance_accounts")
