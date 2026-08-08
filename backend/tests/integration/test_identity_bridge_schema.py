"""M6.5 migration 0190 — bridge columns exist (integration, requires Postgres)."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

pytestmark = pytest.mark.integration

_BRIDGE_COLUMNS = (
    ("context_organizations", "canonical_organization_id"),
    ("context_users", "canonical_user_id"),
    ("context_projects", "canonical_project_id"),
    ("context_sites", "canonical_site_id"),
)


@pytest.fixture
async def engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from mesiri.bootstrap.settings import Settings

    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def test_bridge_columns_present(engine) -> None:
    async with engine.connect() as conn:
        revision = (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
    assert revision >= "0190", f"expected migration >= 0190, got {revision}"

    async with engine.connect() as conn:

        def _check(sync_conn):
            inspector = inspect(sync_conn)
            for table, column in _BRIDGE_COLUMNS:
                cols = {c["name"] for c in inspector.get_columns(table)}
                assert column in cols, f"{table}.{column} missing"

        await conn.run_sync(_check)
