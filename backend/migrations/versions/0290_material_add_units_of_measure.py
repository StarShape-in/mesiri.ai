"""Add units_of_measure + unit_aliases — DB-backed replacement for hardcoded unit synonyms.

Commit 1ad7977 patched around inconsistent unit spelling ("bag"/"bags"/"sack")
with two hardcoded `_UNIT_ALIASES` dicts (canonicalization/builder.py,
runtime/inventory_query.py in the WhatsApp assistant) — one normalizing new
writes, one merging already-stored rows at read time. This migration replaces
that stopgap with a real lookup table so unit resolution has one source of
truth that the WhatsApp assistant, dashboard, and backend can all query.

`units_of_measure` is the fixed global vocabulary (not org-scoped — units like
kg/bags/cum are universal in this domain). `unit_aliases` maps free-text
spelling variants onto a canonical unit; no unit *conversion* is implemented,
only spelling normalization.

`unit_id` is added to material_receipts, material_usage, and
materials_catalog.default_unit_id as a NULLABLE FK and backfilled from the
existing free-text `unit`/`default_unit` values via the same alias map used to
seed unit_aliases. Any value that fails to map aborts the migration loudly
(raises) rather than silently leaving rows unresolved — forces a manual
review of the alias list against real data before this runs against
production. A later migration (0310) tightens unit_id to NOT NULL once all
write paths are updated to require it.

Revision ID: 0290
Revises: 0280
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0290"
down_revision = "0280"
branch_labels = None
depends_on = None

# code -> display name. Canonical codes already implied by commit 1ad7977's
# alias dicts (bags, kg, tons, litres, pieces, rolls, boxes) plus a small set
# of standard construction units. Edit via the units_of_measure table directly
# (or the future catalogue admin UI) if this seed list needs to grow.
_UNITS: list[tuple[str, str]] = [
    ("bags", "Bags"),
    ("kg", "Kilograms"),
    ("tons", "Tons"),
    ("litres", "Litres"),
    ("pieces", "Pieces"),
    ("rolls", "Rolls"),
    ("boxes", "Boxes"),
    ("cum", "Cubic Meters"),
    ("sqm", "Square Meters"),
    ("sqft", "Square Feet"),
    ("mt", "Metric Tons"),
    ("nos", "Numbers"),
]

# canonical code -> alias texts (lowercased). Mirrors the two hardcoded
# _UNIT_ALIASES dicts being retired by this feature.
_ALIASES: dict[str, list[str]] = {
    "bags": ["bag", "sack", "sacks"],
    "kg": ["kgs", "kilogram", "kilograms"],
    "tons": ["ton", "tonne", "tonnes"],
    "litres": ["litre", "liter", "liters", "ltr"],
    "pieces": ["piece", "pc", "pcs"],
    "rolls": ["roll"],
    "boxes": ["box"],
}


def upgrade() -> None:
    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_units_of_measure_code"),
    )

    op.create_table(
        "unit_aliases",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "unit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("units_of_measure.id"),
            nullable=False,
        ),
        sa.Column("alias_text", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("alias_text", name="uq_unit_aliases_alias_text"),
    )
    op.create_index("ix_unit_aliases_unit_id", "unit_aliases", ["unit_id"])

    conn = op.get_bind()
    unit_ids: dict[str, uuid.UUID] = {}
    for code, display_name in _UNITS:
        new_id = uuid.uuid4()
        unit_ids[code] = new_id
        conn.execute(
            sa.text(
                "INSERT INTO units_of_measure (id, code, display_name) "
                "VALUES (:id, :code, :display_name)"
            ),
            {"id": new_id, "code": code, "display_name": display_name},
        )
        # The canonical code itself is always a valid "alias" of itself so a
        # single alias-table lookup resolves both exact codes and synonyms.
        conn.execute(
            sa.text(
                "INSERT INTO unit_aliases (id, unit_id, alias_text) VALUES (:id, :unit_id, :alias_text)"
            ),
            {"id": uuid.uuid4(), "unit_id": new_id, "alias_text": code},
        )

    for code, synonyms in _ALIASES.items():
        for synonym in synonyms:
            conn.execute(
                sa.text(
                    "INSERT INTO unit_aliases (id, unit_id, alias_text) "
                    "VALUES (:id, :unit_id, :alias_text)"
                ),
                {"id": uuid.uuid4(), "unit_id": unit_ids[code], "alias_text": synonym},
            )

    op.add_column(
        "material_receipts",
        sa.Column("unit_id", sa.UUID(as_uuid=True), sa.ForeignKey("units_of_measure.id"), nullable=True),
    )
    op.add_column(
        "material_usage",
        sa.Column("unit_id", sa.UUID(as_uuid=True), sa.ForeignKey("units_of_measure.id"), nullable=True),
    )
    op.add_column(
        "materials_catalog",
        sa.Column(
            "default_unit_id", sa.UUID(as_uuid=True), sa.ForeignKey("units_of_measure.id"), nullable=True
        ),
    )
    op.create_index("ix_material_receipts_unit_id", "material_receipts", ["unit_id"])
    op.create_index("ix_material_usage_unit_id", "material_usage", ["unit_id"])

    for table, unit_col in (
        ("material_receipts", "unit"),
        ("material_usage", "unit"),
        ("materials_catalog", "default_unit"),
    ):
        conn.execute(
            sa.text(
                f"UPDATE {table} t SET unit_id = a.unit_id "  # noqa: S608 - fixed table names, no user input
                "FROM unit_aliases a "
                f"WHERE lower(trim(t.{unit_col})) = a.alias_text "
                "AND t.unit_id IS NULL"
            )
        )
        unmapped = conn.execute(
            sa.text(
                f"SELECT DISTINCT {unit_col} FROM {table} "  # noqa: S608
                f"WHERE {unit_col} IS NOT NULL AND {unit_col} <> '' AND unit_id IS NULL"
            )
        ).fetchall()
        if unmapped:
            values = ", ".join(repr(row[0]) for row in unmapped)
            raise RuntimeError(
                f"Migration 0290: {table}.{unit_col} has values with no unit_aliases match: "
                f"{values}. Add these to the alias seed list (or units_of_measure directly) "
                "and re-run — refusing to silently leave rows unresolved."
            )


def downgrade() -> None:
    op.drop_index("ix_material_usage_unit_id", table_name="material_usage")
    op.drop_column("material_usage", "unit_id")
    op.drop_index("ix_material_receipts_unit_id", table_name="material_receipts")
    op.drop_column("material_receipts", "unit_id")
    op.drop_column("materials_catalog", "default_unit_id")

    op.drop_index("ix_unit_aliases_unit_id", table_name="unit_aliases")
    op.drop_table("unit_aliases")
    op.drop_table("units_of_measure")
