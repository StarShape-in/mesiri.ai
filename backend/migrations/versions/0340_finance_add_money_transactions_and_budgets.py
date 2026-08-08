"""Rename finance_account_transactions to money_transactions; add budgets.

money_transactions keeps the event-sourced ledger from 0080 (account balance
= opening_balance + sum(transactions), never a mutable column) but replaces
the debit/credit + single account_id shape with explicit
from_account_id/to_account_id + transaction_type, matching how money
actually moves in this domain: fund_received (external money in),
transfer (between two money_accounts), expense_payment (money out to an
expense), adjustment, and reversal. No debit/credit terminology.

Backfill mapping from the old (direction, account_id) shape is necessarily a
judgment call since the old schema didn't record enough to distinguish a
transfer leg from a fund receipt:
  - direction='debit', source_type='expense'  -> transaction_type='expense_payment',
    from_account_id=account_id, source re-pointed from the old expense id to
    the matching expense_payments row created in 0330 (expense_payment
    transactions must reference expense_payments, not expenses directly).
  - direction='credit' (any source_type)       -> transaction_type='fund_received',
    to_account_id=account_id (safest default: we cannot tell a transfer's
    receiving leg from new money in without a matching opposite leg, and
    none exists in the old single-row-per-movement schema).
  - anything else (debit, non-expense source)   -> transaction_type='adjustment',
    from_account_id=account_id (safest default for an unrecognized debit).

finance_account_transactions (0080) never carried organization_id of its
own, only account_id — money_transactions.organization_id is backfilled from
the referenced money_accounts row before account_id is dropped.

budgets/budget_allocations are new — lightweight project spending limits,
not accounting periods. Actual spend is always computed from expenses at
read time; no spent_amount/remaining_amount column is stored here.

Revision ID: 0340
Revises: 0330
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0340"
down_revision = "0330"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- finance_account_transactions -> money_transactions ------------------
    op.rename_table("finance_account_transactions", "money_transactions")
    # finance_account_transactions (0080) never carried organization_id itself
    # (only account_id) — backfill it from money_accounts before account_id
    # is dropped below.
    op.add_column(
        "money_transactions", sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "money_transactions",
        sa.Column("from_account_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "money_transactions",
        sa.Column("to_account_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("money_transactions", sa.Column("transaction_type", sa.String(), nullable=True))
    op.add_column("money_transactions", sa.Column("description", sa.String(), nullable=True))
    op.add_column(
        "money_transactions", sa.Column("correlation_id", sa.String(), nullable=True)
    )

    conn.execute(
        sa.text(
            """
            UPDATE money_transactions SET
                from_account_id = CASE WHEN direction = 'debit' THEN account_id END,
                to_account_id = CASE WHEN direction = 'credit' THEN account_id END,
                transaction_type = CASE
                    WHEN direction = 'debit' AND source_type = 'expense' THEN 'expense_payment'
                    WHEN direction = 'credit' THEN 'fund_received'
                    ELSE 'adjustment'
                END
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE money_transactions mt SET organization_id = ma.organization_id
            FROM money_accounts ma
            WHERE ma.id = mt.account_id
            """
        )
    )
    # Re-point expense_payment transactions from the old expense id to the
    # matching expense_payments row (1:1 for backfilled payments — see 0330).
    conn.execute(
        sa.text(
            """
            UPDATE money_transactions mt SET source_id = ep.id, source_type = 'expense_payment'
            FROM expense_payments ep
            WHERE mt.transaction_type = 'expense_payment'
              AND mt.source_type = 'expense'
              AND ep.expense_id = mt.source_id
              AND ep.account_id = mt.from_account_id
            """
        )
    )

    op.alter_column("money_transactions", "transaction_type", nullable=False)
    op.alter_column("money_transactions", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_money_transactions_organization_id",
        "money_transactions",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_index("ix_finance_account_transactions_account_id", table_name="money_transactions")
    op.drop_index("ix_finance_account_transactions_source", table_name="money_transactions")
    op.drop_constraint(
        "finance_account_transactions_account_id_fkey", "money_transactions", type_="foreignkey"
    )
    op.drop_column("money_transactions", "account_id")
    op.drop_column("money_transactions", "direction")

    op.create_foreign_key(
        "fk_money_transactions_from_account_id",
        "money_transactions",
        "money_accounts",
        ["from_account_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_money_transactions_to_account_id",
        "money_transactions",
        "money_accounts",
        ["to_account_id"],
        ["id"],
    )
    op.create_index(
        "ix_money_transactions_from_account_id", "money_transactions", ["from_account_id"]
    )
    op.create_index(
        "ix_money_transactions_to_account_id", "money_transactions", ["to_account_id"]
    )
    op.create_index(
        "ix_money_transactions_source", "money_transactions", ["source_type", "source_id"]
    )
    op.create_index("ix_money_transactions_organization_id", "money_transactions", ["organization_id"])

    op.create_check_constraint(
        "ck_money_transactions_amount_positive", "money_transactions", "amount > 0"
    )
    op.create_check_constraint(
        "ck_money_transactions_type",
        "money_transactions",
        "transaction_type IN ('fund_received', 'transfer', 'expense_payment', 'adjustment', 'reversal')",
    )
    op.create_check_constraint(
        "ck_money_transactions_shape",
        "money_transactions",
        """
        (transaction_type = 'fund_received' AND to_account_id IS NOT NULL AND from_account_id IS NULL)
        OR (transaction_type = 'transfer' AND from_account_id IS NOT NULL AND to_account_id IS NOT NULL
            AND from_account_id != to_account_id)
        OR (transaction_type = 'expense_payment' AND from_account_id IS NOT NULL AND to_account_id IS NULL)
        OR (transaction_type IN ('adjustment', 'reversal')
            AND (from_account_id IS NOT NULL OR to_account_id IS NOT NULL))
        """,
    )

    # --- budgets / budget_allocations -----------------------------------------
    op.create_table(
        "budgets",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
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
    op.create_index("ix_budgets_organization_id", "budgets", ["organization_id"])
    op.create_index("ix_budgets_project_id", "budgets", ["project_id"])
    op.create_check_constraint("ck_budgets_amount_positive", "budgets", "amount > 0")
    op.create_check_constraint("ck_budgets_status", "budgets", "status IN ('active', 'inactive')")
    op.create_check_constraint(
        "ck_budgets_date_order",
        "budgets",
        "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
    )

    op.create_table(
        "budget_allocations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("budget_id", sa.UUID(as_uuid=True), sa.ForeignKey("budgets.id"), nullable=False),
        sa.Column(
            "category_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
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
    op.create_index("ix_budget_allocations_budget_id", "budget_allocations", ["budget_id"])
    op.create_check_constraint(
        "ck_budget_allocations_amount_positive", "budget_allocations", "amount > 0"
    )
    op.create_index(
        "uq_budget_allocations_budget_category",
        "budget_allocations",
        ["budget_id", "category_id"],
        unique=True,
        postgresql_where=sa.text("category_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("budget_allocations")
    op.drop_table("budgets")

    op.drop_constraint("ck_money_transactions_shape", "money_transactions", type_="check")
    op.drop_constraint("ck_money_transactions_type", "money_transactions", type_="check")
    op.drop_constraint("ck_money_transactions_amount_positive", "money_transactions", type_="check")

    op.drop_index("ix_money_transactions_organization_id", table_name="money_transactions")
    op.drop_index("ix_money_transactions_source", table_name="money_transactions")
    op.drop_index("ix_money_transactions_to_account_id", table_name="money_transactions")
    op.drop_index("ix_money_transactions_from_account_id", table_name="money_transactions")
    op.drop_constraint(
        "fk_money_transactions_to_account_id", "money_transactions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_money_transactions_from_account_id", "money_transactions", type_="foreignkey"
    )

    op.add_column("money_transactions", sa.Column("direction", sa.String(), nullable=True))
    op.add_column("money_transactions", sa.Column("account_id", sa.UUID(as_uuid=True), nullable=True))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE money_transactions SET
                direction = CASE WHEN transaction_type = 'fund_received' THEN 'credit' ELSE 'debit' END,
                account_id = COALESCE(from_account_id, to_account_id)
            """
        )
    )
    op.alter_column("money_transactions", "direction", nullable=False)
    op.alter_column("money_transactions", "account_id", nullable=False)
    op.create_foreign_key(
        "finance_account_transactions_account_id_fkey",
        "money_transactions",
        "money_accounts",
        ["account_id"],
        ["id"],
    )
    op.create_index(
        "ix_finance_account_transactions_account_id", "money_transactions", ["account_id"]
    )
    op.create_index(
        "ix_finance_account_transactions_source", "money_transactions", ["source_type", "source_id"]
    )

    op.drop_column("money_transactions", "correlation_id")
    op.drop_column("money_transactions", "description")
    op.drop_column("money_transactions", "transaction_type")
    op.drop_column("money_transactions", "to_account_id")
    op.drop_column("money_transactions", "from_account_id")
    op.drop_constraint(
        "fk_money_transactions_organization_id", "money_transactions", type_="foreignkey"
    )
    op.drop_column("money_transactions", "organization_id")
    op.rename_table("money_transactions", "finance_account_transactions")
