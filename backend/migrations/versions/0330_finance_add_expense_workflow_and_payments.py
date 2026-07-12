"""Add expense workflow/payment fields, expense_attachments, expense_payments.

Splits "what was the expense" from "how was it paid": expenses gains
workflow_status (draft/pending_confirmation/confirmed/rejected/voided) and
payment_status (unpaid/partially_paid/paid/reimbursable/reimbursed) instead
of being implicitly "paid" via a direct account_id. Existing rows are all
real, already-happened expenses recorded before this workflow existed, so
they backfill to workflow_status='confirmed'; payment_status backfills to
'paid' when the expense already had an account_id (one implicit payment
covering the full amount) or 'unpaid' otherwise.

expense_attachments replaces the single receipt_media_object_key column so
an expense can carry multiple pieces of evidence (receipt, bill, payment
proof, ...). expense_payments replaces the direct expenses.account_id link
so an expense can have zero, one, or several payments (including split
payments across accounts) instead of exactly one implicit account. Each
backfilled payment is marked 'confirmed' — it represents money that, per the
existing data, was already recorded as spent from that account.

`category`, `account_id` and `receipt_media_object_key` are dropped at the
end of this migration only after their replacements (`category_id` backfilled
in 0320, expense_payments, expense_attachments) are fully populated.

Revision ID: 0330
Revises: 0320
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0330"
down_revision = "0320"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- expenses: workflow/payment status, expense_number, source tracing --
    op.add_column(
        "expenses",
        sa.Column("expense_number", sa.String(), nullable=True),
    )
    op.add_column(
        "expenses",
        sa.Column(
            "workflow_status", sa.String(), nullable=False, server_default="pending_confirmation"
        ),
    )
    op.add_column(
        "expenses",
        sa.Column("payment_status", sa.String(), nullable=False, server_default="unpaid"),
    )
    op.add_column("expenses", sa.Column("source_message_id", sa.String(), nullable=True))

    # Existing rows predate the workflow — they are real, already-recorded
    # expenses, so they backfill straight to 'confirmed'. Payment status
    # backfills from whether the expense already had a paying account.
    conn.execute(sa.text("UPDATE expenses SET workflow_status = 'confirmed'"))
    conn.execute(
        sa.text(
            "UPDATE expenses SET payment_status = 'paid' WHERE account_id IS NOT NULL"
        )
    )

    op.create_check_constraint(
        "ck_expenses_workflow_status",
        "expenses",
        "workflow_status IN ('draft', 'pending_confirmation', 'confirmed', 'rejected', 'voided')",
    )
    op.create_check_constraint(
        "ck_expenses_payment_status",
        "expenses",
        "payment_status IN ('unpaid', 'partially_paid', 'paid', 'reimbursable', 'reimbursed')",
    )
    op.create_check_constraint("ck_expenses_amount_positive", "expenses", "amount > 0")
    op.create_index("ix_expenses_workflow_status", "expenses", ["workflow_status"])
    op.create_index("ix_expenses_payment_status", "expenses", ["payment_status"])

    # --- expense_attachments -------------------------------------------------
    op.create_table(
        "expense_attachments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expense_id", sa.UUID(as_uuid=True), sa.ForeignKey("expenses.id"), nullable=False
        ),
        sa.Column("media_object_key", sa.String(), nullable=False),
        sa.Column("attachment_type", sa.String(), nullable=False, server_default="receipt"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_expense_attachments_expense_id", "expense_attachments", ["expense_id"])
    op.create_check_constraint(
        "ck_expense_attachments_type",
        "expense_attachments",
        "attachment_type IN ('receipt', 'bill', 'payment_proof', 'supporting_image', 'other')",
    )

    receipt_rows = conn.execute(
        sa.text(
            "SELECT id, receipt_media_object_key, created_at, created_by FROM expenses "
            "WHERE receipt_media_object_key IS NOT NULL"
        )
    ).fetchall()
    for row in receipt_rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO expense_attachments (id, expense_id, media_object_key, attachment_type, created_at, created_by)
                VALUES (:id, :expense_id, :media_object_key, 'receipt', :created_at, :created_by)
                """
            ),
            {
                "id": uuid.uuid4(),
                "expense_id": row.id,
                "media_object_key": row.receipt_media_object_key,
                "created_at": row.created_at,
                "created_by": row.created_by,
            },
        )

    # --- expense_payments -----------------------------------------------------
    op.create_table(
        "expense_payments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "expense_id", sa.UUID(as_uuid=True), sa.ForeignKey("expenses.id"), nullable=False
        ),
        sa.Column(
            "account_id", sa.UUID(as_uuid=True), sa.ForeignKey("money_accounts.id"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("reference_number", sa.String(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=False),
        sa.Column("paid_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="confirmed"),
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
    op.create_index("ix_expense_payments_expense_id", "expense_payments", ["expense_id"])
    op.create_index("ix_expense_payments_account_id", "expense_payments", ["account_id"])
    op.create_index("ix_expense_payments_organization_id", "expense_payments", ["organization_id"])
    op.create_check_constraint(
        "ck_expense_payments_amount_positive", "expense_payments", "amount > 0"
    )
    op.create_check_constraint(
        "ck_expense_payments_status",
        "expense_payments",
        "status IN ('pending', 'confirmed', 'reversed')",
    )

    paid_rows = conn.execute(
        sa.text(
            "SELECT id, organization_id, account_id, amount, occurred_date, occurred_time, "
            "created_at, created_by FROM expenses WHERE account_id IS NOT NULL"
        )
    ).fetchall()
    # expense_id -> expense_payments.id, kept so 0340 can re-point old
    # finance_account_transactions(source_type='expense') rows at the new
    # expense_payments row instead of the expense itself.
    for row in paid_rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO expense_payments
                    (id, organization_id, expense_id, account_id, amount, paid_date, paid_time,
                     status, created_at, created_by, updated_at)
                VALUES
                    (:id, :organization_id, :expense_id, :account_id, :amount, :paid_date, :paid_time,
                     'confirmed', :created_at, :created_by, :created_at)
                """
            ),
            {
                "id": uuid.uuid4(),
                "organization_id": row.organization_id,
                "expense_id": row.id,
                "account_id": row.account_id,
                "amount": row.amount,
                "paid_date": row.occurred_date,
                "paid_time": row.occurred_time,
                "created_at": row.created_at,
                "created_by": row.created_by,
            },
        )

    # --- drop superseded columns ----------------------------------------------
    op.alter_column("expenses", "category_id", nullable=False)
    op.drop_column("expenses", "category")

    op.drop_index("ix_expenses_account_id", table_name="expenses")
    op.drop_constraint("expenses_account_id_fkey", "expenses", type_="foreignkey")
    op.drop_column("expenses", "account_id")

    op.drop_column("expenses", "receipt_media_object_key")


def downgrade() -> None:
    op.add_column("expenses", sa.Column("receipt_media_object_key", sa.String(), nullable=True))
    op.add_column(
        "expenses",
        sa.Column("account_id", sa.UUID(as_uuid=True), sa.ForeignKey("money_accounts.id"), nullable=True),
    )
    op.create_index("ix_expenses_account_id", "expenses", ["account_id"])
    op.add_column(
        "expenses", sa.Column("category", sa.String(), nullable=False, server_default="petty_cash")
    )
    op.alter_column("expenses", "category_id", nullable=True)

    op.drop_table("expense_payments")
    op.drop_table("expense_attachments")

    op.drop_index("ix_expenses_payment_status", table_name="expenses")
    op.drop_index("ix_expenses_workflow_status", table_name="expenses")
    op.drop_constraint("ck_expenses_amount_positive", "expenses", type_="check")
    op.drop_constraint("ck_expenses_payment_status", "expenses", type_="check")
    op.drop_constraint("ck_expenses_workflow_status", "expenses", type_="check")
    op.drop_column("expenses", "source_message_id")
    op.drop_column("expenses", "payment_status")
    op.drop_column("expenses", "workflow_status")
    op.drop_column("expenses", "expense_number")
