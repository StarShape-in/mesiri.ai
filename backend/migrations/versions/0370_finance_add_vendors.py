"""Add vendors table and expenses.vendor_id FK.

Fixes a schema drift, not new design: `Expense.vendor_id`
(domains/expenses/entities.py) and the `domains/vendors/` package already
exist, but no prior migration ever created a `vendors` table or an
`expenses.vendor_id` column -- the entity field has been silently `None`
since it was added. `vendors` mirrors `expense_categories`'s shape from
0320 exactly (org-scoped name + status, same unique-name/index/check-
constraint conventions) since both are simple named lookup entities
resolved from free text at expense-capture time (see
application/vendors/resolution.py).

Revision ID: 0370
Revises: 0369
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0370"
down_revision = "0369"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
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
    op.create_index("ix_vendors_organization_id", "vendors", ["organization_id"])
    op.create_unique_constraint("uq_vendors_org_name", "vendors", ["organization_id", "name"])
    op.create_check_constraint("ck_vendors_status", "vendors", "status IN ('active', 'inactive')")

    op.add_column("expenses", sa.Column("vendor_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_expenses_vendor_id", "expenses", "vendors", ["vendor_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_expenses_vendor_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "vendor_id")

    op.drop_constraint("ck_vendors_status", "vendors", type_="check")
    op.drop_constraint("uq_vendors_org_name", "vendors", type_="unique")
    op.drop_index("ix_vendors_organization_id", table_name="vendors")
    op.drop_table("vendors")
