"""Add movement_reason, notes, reverses_movement_id to material_receipts/material_usage (Materials V1 UI).

Dashboard Materials surface (Inflows/Outflows/Inventory) needs a reason code
per movement so the UI can render "Received" vs "Transfer In" vs "Adjustment
In" etc. and enforce valid direction/reason combinations. `material_receipts`
rows are the IN direction, `material_usage` rows are the OUT direction (see
migration 0090's rationale for keeping two tables instead of one with a
direction flag) — reason values are therefore scoped per-table with a CHECK
constraint rather than a single shared enum.

`reverses_movement_id` (self-referencing, nullable) supports the immutable-
ledger correction workflow: confirmed movements are never edited/deleted;
a correction inserts a new opposite-direction adjustment row that references
the movement it corrects, preserving full audit history.

`notes` is a free-text field for correction context / usage/destination
context not already covered by `supplier`/`work_item`.

A CHECK constraint on `quantity > 0` is added defensively — the app layer
already validates this, but a DB constraint prevents corruption from any
future direct-write path.

Revision ID: 0270
Revises: 0260
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0270"
down_revision = "0260"
branch_labels = None
depends_on = None

_RECEIPT_REASONS = ("RECEIVED", "TRANSFER_IN", "RETURN_IN", "ADJUSTMENT_IN")
_USAGE_REASONS = ("CONSUMED", "TRANSFER_OUT", "RETURN_TO_VENDOR", "WASTAGE", "ADJUSTMENT_OUT")


def upgrade() -> None:
    op.add_column(
        "material_receipts",
        sa.Column("movement_reason", sa.String(), nullable=False, server_default="RECEIVED"),
    )
    op.add_column("material_receipts", sa.Column("notes", sa.String(), nullable=True))
    op.add_column(
        "material_receipts",
        sa.Column(
            "reverses_movement_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_usage.id"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_material_receipts_movement_reason",
        "material_receipts",
        sa.text("movement_reason IN ('" + "','".join(_RECEIPT_REASONS) + "')"),
    )
    op.create_check_constraint(
        "ck_material_receipts_quantity_positive", "material_receipts", sa.text("quantity > 0")
    )
    op.create_index(
        "ix_material_receipts_movement_reason", "material_receipts", ["movement_reason"]
    )

    op.add_column(
        "material_usage",
        sa.Column("movement_reason", sa.String(), nullable=False, server_default="CONSUMED"),
    )
    op.add_column("material_usage", sa.Column("notes", sa.String(), nullable=True))
    op.add_column(
        "material_usage",
        sa.Column(
            "reverses_movement_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_receipts.id"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_material_usage_movement_reason",
        "material_usage",
        sa.text("movement_reason IN ('" + "','".join(_USAGE_REASONS) + "')"),
    )
    op.create_check_constraint(
        "ck_material_usage_quantity_positive", "material_usage", sa.text("quantity > 0")
    )
    op.create_index("ix_material_usage_movement_reason", "material_usage", ["movement_reason"])


def downgrade() -> None:
    op.drop_index("ix_material_usage_movement_reason", table_name="material_usage")
    op.drop_constraint("ck_material_usage_quantity_positive", "material_usage", type_="check")
    op.drop_constraint("ck_material_usage_movement_reason", "material_usage", type_="check")
    op.drop_column("material_usage", "reverses_movement_id")
    op.drop_column("material_usage", "notes")
    op.drop_column("material_usage", "movement_reason")

    op.drop_index("ix_material_receipts_movement_reason", table_name="material_receipts")
    op.drop_constraint("ck_material_receipts_quantity_positive", "material_receipts", type_="check")
    op.drop_constraint("ck_material_receipts_movement_reason", "material_receipts", type_="check")
    op.drop_column("material_receipts", "reverses_movement_id")
    op.drop_column("material_receipts", "notes")
    op.drop_column("material_receipts", "movement_reason")
