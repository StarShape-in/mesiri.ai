"""Rename finance_accounts to money_accounts; add expense_categories.

Mesiri Daily is not an accounting system — money_accounts tracks where
operational money sits (cash/bank/employee advances), not a full chart of
accounts. Renaming finance_accounts -> money_accounts preserves ids, opening
balances and history; `account_name` becomes `name` and we add
project_id/site_id/owner_user_id scoping plus the `employee_advance`/`other`
account types (employee advances are just money_accounts with
account_type='employee_advance' and owner_user_id set — no separate table).

expense_categories is new: organization-scoped, configurable "why money was
spent" list. Existing `expenses.category` free-text values (today locked to
the single value 'petty_cash' — see 0100's docstring) are backfilled into one
category row per distinct value per organization, and `expenses.category_id`
is added (nullable for now; a later migration backfills it before dropping
the old `category` column, since we still need `category` readable until
that backfill runs).

Revision ID: 0320
Revises: 0310
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0320"
down_revision = "0310"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- finance_accounts -> money_accounts -------------------------------
    op.rename_table("finance_accounts", "money_accounts")
    op.alter_column("money_accounts", "account_name", new_column_name="name")
    op.add_column("money_accounts", sa.Column("project_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("money_accounts", sa.Column("site_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "money_accounts", sa.Column("owner_user_id", sa.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_money_accounts_project_id", "money_accounts", "projects", ["project_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_money_accounts_site_id", "money_accounts", "sites", ["site_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_money_accounts_owner_user_id", "money_accounts", "users", ["owner_user_id"], ["id"]
    )

    # Existing rows only ever used 'active'/'closed' (see 0080); normalize
    # 'closed' -> 'inactive' to match the new two-state status convention
    # used across expense_categories/budgets below.
    conn.execute(sa.text("UPDATE money_accounts SET status = 'inactive' WHERE status = 'closed'"))

    op.drop_index("ix_finance_accounts_organization_id", table_name="money_accounts")
    op.create_index("ix_money_accounts_organization_id", "money_accounts", ["organization_id"])
    op.create_index("ix_money_accounts_project_id", "money_accounts", ["project_id"])
    op.create_index("ix_money_accounts_owner_user_id", "money_accounts", ["owner_user_id"])

    op.create_check_constraint(
        "ck_money_accounts_account_type",
        "money_accounts",
        "account_type IN ('cash', 'bank', 'employee_advance', 'other')",
    )
    op.create_check_constraint(
        "ck_money_accounts_status", "money_accounts", "status IN ('active', 'inactive')"
    )
    op.create_check_constraint(
        "ck_money_accounts_opening_balance_non_negative",
        "money_accounts",
        "opening_balance >= 0",
    )

    # --- expense_categories -------------------------------------------------
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column(
            "parent_category_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id"),
            nullable=True,
        ),
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
    op.create_index(
        "ix_expense_categories_organization_id", "expense_categories", ["organization_id"]
    )
    op.create_unique_constraint(
        "uq_expense_categories_org_name", "expense_categories", ["organization_id", "name"]
    )
    op.create_index(
        "uq_expense_categories_org_code",
        "expense_categories",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_expense_categories_status", "expense_categories", "status IN ('active', 'inactive')"
    )

    op.add_column("expenses", sa.Column("category_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_expenses_category_id", "expenses", "expense_categories", ["category_id"], ["id"]
    )

    # One expense_categories row per distinct (organization_id, category
    # text) pair actually in use, then point expenses.category_id at it.
    # System user (created_by) for generated rows: reuse the creator of the
    # first expense in that (org, category) group — avoids inventing a
    # synthetic "system" user that doesn't exist in `users`.
    distinct_pairs = conn.execute(
        sa.text(
            """
            SELECT DISTINCT ON (organization_id, category)
                organization_id, category, created_by
            FROM expenses
            ORDER BY organization_id, category, created_at ASC
            """
        )
    ).fetchall()
    for row in distinct_pairs:
        category_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO expense_categories (id, organization_id, name, status, created_by, created_at, updated_at)
                VALUES (:id, :organization_id, :name, 'active', :created_by, now(), now())
                """
            ),
            {
                "id": category_id,
                "organization_id": row.organization_id,
                "name": row.category,
                "created_by": row.created_by,
            },
        )
        conn.execute(
            sa.text(
                """
                UPDATE expenses SET category_id = :category_id
                WHERE organization_id = :organization_id AND category = :category
                """
            ),
            {
                "category_id": category_id,
                "organization_id": row.organization_id,
                "category": row.category,
            },
        )


def downgrade() -> None:
    op.drop_constraint("fk_expenses_category_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "category_id")

    op.drop_table("expense_categories")

    op.drop_constraint(
        "ck_money_accounts_opening_balance_non_negative", "money_accounts", type_="check"
    )
    op.drop_constraint("ck_money_accounts_status", "money_accounts", type_="check")
    op.drop_constraint("ck_money_accounts_account_type", "money_accounts", type_="check")

    op.drop_index("ix_money_accounts_owner_user_id", table_name="money_accounts")
    op.drop_index("ix_money_accounts_project_id", table_name="money_accounts")
    op.drop_index("ix_money_accounts_organization_id", table_name="money_accounts")
    op.create_index("ix_finance_accounts_organization_id", "money_accounts", ["organization_id"])

    op.drop_constraint("fk_money_accounts_owner_user_id", "money_accounts", type_="foreignkey")
    op.drop_constraint("fk_money_accounts_site_id", "money_accounts", type_="foreignkey")
    op.drop_constraint("fk_money_accounts_project_id", "money_accounts", type_="foreignkey")
    op.drop_column("money_accounts", "owner_user_id")
    op.drop_column("money_accounts", "site_id")
    op.drop_column("money_accounts", "project_id")
    op.alter_column("money_accounts", "name", new_column_name="account_name")
    op.rename_table("money_accounts", "finance_accounts")
