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

material_id/unit_id on material_receipts/material_usage are already fully
resolved by 0290/0300's backfill + self-heal — this migration just tightens
those two to NOT NULL. materials_catalog.default_unit_id needs one more
backfill pass here first: catalog entries created directly (dashboard's old
create_material endpoint, or 0300's fallback catalog-row creation for
never-cataloged materials) may never have had a Stock Unit assigned at all.
Backfilled from the unit most commonly reported in that material's own
movement history (the strongest real signal, now available since 0300 fully
resolved material_movements); anything with zero movement history falls
back to a generic "unspecified" unit (admin can correct via the catalogue
surface later) rather than blocking this migration.

Revision ID: 0310
Revises: 0300
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0310"
down_revision = "0300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Prefer the unit most commonly used in this material's own movement
    # history.
    conn.execute(
        sa.text(
            """
            UPDATE materials_catalog c SET default_unit_id = ranked.unit_id
            FROM (
                SELECT DISTINCT ON (material_id) material_id, unit_id
                FROM (
                    SELECT material_id, unit_id, COUNT(*) AS cnt
                    FROM material_movements
                    GROUP BY material_id, unit_id
                ) counts
                ORDER BY material_id, cnt DESC
            ) ranked
            WHERE c.id = ranked.material_id AND c.default_unit_id IS NULL
            """
        )
    )

    # Anything left (materials never referenced by any movement at all) gets
    # a generic fallback unit rather than blocking this migration.
    remaining = conn.execute(
        sa.text("SELECT COUNT(*) FROM materials_catalog WHERE default_unit_id IS NULL")
    ).scalar_one()
    if remaining:
        fallback_id = conn.execute(
            sa.text("SELECT id FROM units_of_measure WHERE code = 'unspecified'")
        ).scalar()
        if fallback_id is None:
            fallback_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    "INSERT INTO units_of_measure (id, code, display_name) "
                    "VALUES (:id, 'unspecified', 'Unspecified')"
                ),
                {"id": fallback_id},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO unit_aliases (id, unit_id, alias_text) "
                    "VALUES (:id, :unit_id, 'unspecified')"
                ),
                {"id": uuid.uuid4(), "unit_id": fallback_id},
            )
        conn.execute(
            sa.text(
                "UPDATE materials_catalog SET default_unit_id = :fallback_id "
                "WHERE default_unit_id IS NULL"
            ),
            {"fallback_id": fallback_id},
        )

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
