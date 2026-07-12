"""Migration 0290 + 0310 self-heal invariants.

0290's self-heal: any free-text unit value in material_receipts/
material_usage/materials_catalog that doesn't match the hardcoded alias
list (including regional-language text like Malayalam "ചാക്ക്") gets a
fallback units_of_measure row auto-created rather than aborting the
migration. The alias resolution service (UnitsOfMeasureRepository.
resolve_alias) is the runtime-visible end of this -- a unit reported as
"ചാക്ക്" or "BAG" or "  sacks  " must all resolve to the canonical
"bags" unit.

0310's self-heal: materials_catalog.default_unit_id becomes NOT NULL.
Catalog rows with movement history get their unit backfilled from the
most-common movement's unit; rows with no movement history get a
synthetic "unspecified" unit, so the NOT NULL constraint can never fail
on real data.

These tests assert the post-migration invariants on a live DB at head
(>= 0310), plus the runtime alias-resolution behavior 0290 established.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.materials import (
    UnitsOfMeasureRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def test_0290_alias_resolution_handles_malayalam_casing_and_whitespace(
    engine: AsyncEngine,
):
    """0290's _ALIASES seed includes Malayalam variants (e.g. "ചാക്ക്" = bags)
    and the alias lookup is case/whitespace-insensitive. resolve_alias
    (materials.py:693) is the runtime-visible end of the migration's self-
    heal: a WhatsApp report saying "ചാക്ക്" or "BAG" or "  sacks  " must all
    resolve to the canonical "bags" unit. If any of these fail, the
    migration's alias seed is incomplete and a real WhatsApp report would
    hit a Stock Unit mismatch clarification unnecessarily."""
    async with engine.connect() as conn:
        rev = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0290":
        pytest.skip(f"database at {rev}, need >= 0290")

    async with engine.connect() as conn:
        repo = UnitsOfMeasureRepository(conn)
        cases = [
            ("ചാക്ക്", "bags"),  # Malayalam for sack/bag
            ("BAG", "bags"),  # uppercase singular
            ("  sacks  ", "bags"),  # leading/trailing whitespace, plural
            ("Kgs", "kg"),  # mixed case
            ("kgs", "kg"),  # lowercase plural
            ("litre", "litres"),  # singular -> plural canonical
            ("Ltr", "litres"),  # abbreviation, mixed case
        ]
        for raw, expected_code in cases:
            resolved = await repo.resolve_alias(raw)
            assert resolved is not None, (
                f"0290 alias resolution must handle {raw!r} -> {expected_code}"
            )
            assert resolved["code"] == expected_code, (
                f"0290 alias {raw!r} resolved to {resolved['code']!r}, "
                f"expected {expected_code!r}"
            )


async def test_0310_default_unit_id_is_not_null_on_catalog(engine: AsyncEngine):
    """0310:106 makes materials_catalog.default_unit_id NOT NULL -- this is
    the constraint that enforces 'every catalog entry has a Stock Unit' at
    the DB level. If a future migration loosens it back to nullable, stock
    derivation and the WhatsApp unit-mismatch gate both lose their
    foundation. Asserting the schema-level constraint directly is the
    strongest reachable invariant."""
    async with engine.connect() as conn:
        rev = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0310":
        pytest.skip(f"database at {rev}, need >= 0310")

    async with engine.connect() as conn:
        for table, column in [
            ("materials_catalog", "default_unit_id"),
            ("material_receipts", "material_id"),
            ("material_receipts", "unit_id"),
            ("material_usage", "material_id"),
            ("material_usage", "unit_id"),
        ]:
            nullable = (
                await conn.execute(
                    sa.text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c"
                    ),
                    {"t": table, "c": column},
                )
            ).scalar_one()
            assert nullable == "NO", (
                f"0310 must leave {table}.{column} NOT NULL; found nullable={nullable!r}"
            )


async def test_0310_no_catalog_row_has_null_default_unit_id(engine: AsyncEngine):
    """Downstream of the NOT NULL constraint: no existing catalog row should
    actually have a NULL default_unit_id. 0310's backfill (most-common-
    movement unit, then synthetic 'unspecified' fallback) is supposed to
    guarantee this holds on real data. A NULL here would mean the backfill
    missed a row -- which would block the NOT NULL constraint from being
    added in a fresh deploy."""
    async with engine.connect() as conn:
        rev = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0310":
        pytest.skip(f"database at {rev}, need >= 0310")

    async with engine.connect() as conn:
        null_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM materials_catalog WHERE default_unit_id IS NULL"
                )
            )
        ).scalar_one()
        assert null_count == 0, (
            f"0310's backfill must resolve every catalog row's default_unit_id; "
            f"found {null_count} NULL"
        )


async def test_0310_unspecified_fallback_unit_exists_when_any_catalog_row_needs_it(
    engine: AsyncEngine,
):
    """0310:79 creates a synthetic 'unspecified' units_of_measure row iff any
    catalog row had no movement history to backfill default_unit_id from.
    On a live DB, if the 'unspecified' unit exists, it must be active and
    resolvable via its own alias (so the WhatsApp unit-resolution gate can
    still match it). If it doesn't exist, that's fine -- it means every
    catalog row had movement history. This test asserts the conditional
    invariant either way."""
    async with engine.connect() as conn:
        rev = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0310":
        pytest.skip(f"database at {rev}, need >= 0310")

    async with engine.connect() as conn:
        unspecified = (
            await conn.execute(
                sa.text("SELECT id, is_active FROM units_of_measure WHERE code = 'unspecified'")
            )
        ).mappings().first()

    if unspecified is None:
        # Every catalog row had movement history -- the fallback was never
        # needed. This is the happy path on a well-populated DB.
        return

    assert unspecified["is_active"] is True, (
        "the 'unspecified' fallback unit must be active so it can be resolved"
    )
    async with engine.connect() as conn:
        repo = UnitsOfMeasureRepository(conn)
        resolved = await repo.resolve_alias("unspecified")
        assert resolved is not None, (
            "the 'unspecified' unit must resolve via its own self-alias"
        )
        assert resolved["code"] == "unspecified"
