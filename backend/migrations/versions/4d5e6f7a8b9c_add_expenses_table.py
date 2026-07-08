"""Add expenses table — v1 scope is petty cash only.

`account_id` links to finance_accounts; the debit itself is recorded as a
finance_account_transactions row (application layer), never by mutating a
balance column directly.

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-07-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("account_id", sa.UUID(as_uuid=True), sa.ForeignKey("finance_accounts.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("description", sa.String(), nullable=True),
        # Fixed in v1 — no other expense types (architecture: "v1 scope locked").
        sa.Column("category", sa.String(), nullable=False, server_default="petty_cash"),
        sa.Column("receipt_media_object_key", sa.String(), nullable=True),
        sa.Column("occurred_date", sa.Date(), nullable=False),
        sa.Column("occurred_time", sa.Time(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
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
    op.create_index("ix_expenses_org_project", "expenses", ["organization_id", "project_id"])
    op.create_index("ix_expenses_site_id", "expenses", ["site_id"])
    op.create_index("ix_expenses_account_id", "expenses", ["account_id"])
    op.create_index("ix_expenses_occurred_date", "expenses", ["occurred_date"])
    op.create_index("ix_expenses_correlation_id", "expenses", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_correlation_id", table_name="expenses")
    op.drop_index("ix_expenses_occurred_date", table_name="expenses")
    op.drop_index("ix_expenses_account_id", table_name="expenses")
    op.drop_index("ix_expenses_site_id", table_name="expenses")
    op.drop_index("ix_expenses_org_project", table_name="expenses")
    op.drop_table("expenses")
