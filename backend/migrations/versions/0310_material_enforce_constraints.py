"""Enforce final constraints for Materials V2 (catalog/unit/ledger closed set).

By the time this migration runs, application code (backend router + CQRS
handler, WhatsApp assistant resolution gates, dashboard entry forms) has been
updated to require material_id/unit_id on every write — 0290/0300 only added
the columns nullable so the transition could land without a hard cutover.
This migration removes the escape hatch:

- material_receipts.material_id/unit_id and material_usage.material_id/unit_id
  become NOT NULL — free-text-only rows are no longer possible.
- materials_catalog.default_unit_id becomes NOT NULL — every catalog entry
  has an enforced Stock Unit (see domains/materials/router.py's
  _resolve_and_validate_material_unit).
- UNIQUE(source_type, source_id, movement_type) on material_movements is the
  idempotency guard for the REST write path (which has no idempotency_keys
  claim like the CQRS path does) — a retried movement-post for the same
  already-created receipt/usage row fails cleanly instead of double-posting
  (see domains/materials/posting.py's docstring).

Run only after confirming (via the application layer) that no NULL
material_id/unit_id/default_unit_id rows remain — this migration does not
attempt to backfill; 0290/0300 already did, and abort loudly if they didn't
finish cleanly. This migration itself will fail with a NOT NULL violation if
any row was missed, which is the intended safety net.

Revision ID: 0310
Revises: 0300
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0310"
down_revision = "0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("material_receipts", "unit_id", nullable=False)
    op.alter_column("material_receipts", "material_id", nullable=False)
    op.alter_column("material_usage", "unit_id", nullable=False)
    op.alter_column("material_usage", "material_id", nullable=False)
    op.alter_column("materials_catalog", "default_unit_id", nullable=False)

    op.create_unique_constraint(
        "uq_material_movements_source",
        "material_movements",
        ["source_type", "source_id", "movement_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_material_movements_source", "material_movements", type_="unique")

    op.alter_column("materials_catalog", "default_unit_id", nullable=True)
    op.alter_column("material_usage", "material_id", nullable=True)
    op.alter_column("material_usage", "unit_id", nullable=True)
    op.alter_column("material_receipts", "material_id", nullable=True)
    op.alter_column("material_receipts", "unit_id", nullable=True)
