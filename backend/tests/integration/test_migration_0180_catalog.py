"""Migration 0180 materials_catalog backfill must not use MIN(uuid).

Postgres has no aggregate min(uuid). The migration uses
(MIN(created_by::text))::uuid instead.
"""

from __future__ import annotations

import pytest


def test_0180_backfill_sql_does_not_use_min_uuid():
    """Guard against reintroducing MIN(uuid) in 0180 backfill."""
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "0180_material_add_catalog.py"
    )
    source = migration.read_text(encoding="utf-8")
    assert "MIN(created_by)" not in source or "MIN(created_by::text)" in source
    assert "(MIN(created_by::text))::uuid" in source


pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from mesiri.bootstrap.settings import Settings

    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def test_0180_migration_applied_when_at_head(engine) -> None:
    """On integration Postgres at >=0180, materials_catalog exists."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        rev = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    if rev < "0180":
        pytest.skip(f"database at {rev}, need >= 0180")

    async with engine.connect() as conn:
        exists = (
            await conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'materials_catalog')"
                )
            )
        ).scalar_one()
    assert exists is True
