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
seed unit_aliases. Any value that fails to map against the known alias list
(production data includes regional-language unit text, e.g. Malayalam) gets
a fallback units_of_measure row auto-created from the raw text, rather than
aborting the migration — a mid-migration abort leaves a deploy half-applied
(new code on disk, old schema still live, service never restarted; see the
deploy workflow's health-check/rollback path, which only runs if migrations
succeed). Fallback units are logged during the migration for later
review/cleanup. A later migration (0310) tightens unit_id to NOT NULL once
all write paths are updated to require it.

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
# _UNIT_ALIASES dicts being retired by this feature, plus regional-language
# spellings observed in real WhatsApp reports (e.g. Malayalam "ചാക്ക്" =
# sack/bag) — this codebase's users report in more than English.
_ALIASES: dict[str, list[str]] = {
    "bags": ["bag", "sack", "sacks", "ചാക്ക്"],
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

    # Any value still unmapped after the known alias list is a real spelling/
    # language variant this migration didn't anticipate (production data has
    # included regional-language unit text, e.g. Malayalam). Rather than
    # aborting the whole migration on unknown production data — which leaves
    # the deploy half-applied (new code checked out, old schema still live,
    # service never restarted; see the deploy workflow's health-check/
    # rollback path, which is never reached if this migration raises) — treat
    # the raw text itself as a new fallback unit: create a units_of_measure
    # row + self-alias for it (visible in the migration log for later
    # cleanup/renaming, e.g. via the catalogue admin surface), then map to
    # it. This guarantees the migration always completes in one deploy.
    for table, unit_col, target_col in (
        ("material_receipts", "unit", "unit_id"),
        ("material_usage", "unit", "unit_id"),
        ("materials_catalog", "default_unit", "default_unit_id"),
    ):
        conn.execute(
            sa.text(
                f"UPDATE {table} t SET {target_col} = a.unit_id "  # noqa: S608 - fixed table/column names, no user input
                "FROM unit_aliases a "
                f"WHERE lower(trim(t.{unit_col})) = a.alias_text "
                f"AND t.{target_col} IS NULL"
            )
        )
        unmapped = conn.execute(
            sa.text(
                f"SELECT DISTINCT {unit_col} FROM {table} "  # noqa: S608
                f"WHERE {unit_col} IS NOT NULL AND {unit_col} <> '' AND {target_col} IS NULL"
            )
        ).fetchall()
        for (raw_value,) in unmapped:
            fallback_code = raw_value.strip().lower()
            fallback_unit_id = conn.execute(
                sa.text("SELECT id FROM units_of_measure WHERE code = :code"),
                {"code": fallback_code},
            ).scalar()
            if fallback_unit_id is None:
                fallback_unit_id = uuid.uuid4()
                conn.execute(
                    sa.text(
                        "INSERT INTO units_of_measure (id, code, display_name) "
                        "VALUES (:id, :code, :display_name)"
                    ),
                    {"id": fallback_unit_id, "code": fallback_code, "display_name": raw_value.strip()},
                )
                print(  # noqa: T201 - deliberately surfaced in deploy log for follow-up cleanup
                    f"Migration 0290: created fallback unit {fallback_code!r} for "
                    f"{table}.{unit_col} value {raw_value!r} (no existing alias matched)"
                )
            conn.execute(
                sa.text(
                    "INSERT INTO unit_aliases (id, unit_id, alias_text) VALUES (:id, :unit_id, :alias_text) "
                    "ON CONFLICT (alias_text) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "unit_id": fallback_unit_id, "alias_text": fallback_code},
            )

        conn.execute(
            sa.text(
                f"UPDATE {table} t SET {target_col} = a.unit_id "  # noqa: S608
                "FROM unit_aliases a "
                f"WHERE lower(trim(t.{unit_col})) = a.alias_text "
                f"AND t.{target_col} IS NULL"
            )
        )
        still_unmapped = conn.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                f"WHERE {unit_col} IS NOT NULL AND {unit_col} <> '' AND {target_col} IS NULL"
            )
        ).scalar_one()
        if still_unmapped:
            raise RuntimeError(
                f"Migration 0290: {still_unmapped} {table} rows still unmapped after fallback "
                f"unit creation — this should be unreachable; investigate {table}.{unit_col} data."
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
