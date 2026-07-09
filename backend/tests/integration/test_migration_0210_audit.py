"""Migration 0210 adds audit columns + debug tables.

Verifies that G1-G5 changes are present when the DB is at >= 0210.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from mesiri.bootstrap.settings import Settings

    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def _db_rev(engine) -> str:
    from sqlalchemy import text

    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()


async def _columns(engine, table: str) -> set[str]:
    from sqlalchemy import text

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :t"
                ),
                {"t": table},
            )
        ).fetchall()
    return {r[0] for r in rows}


async def test_0210_rbac_has_created_at(engine) -> None:
    """G1: RBAC junction tables gain created_at."""
    if await _db_rev(engine) < "0210":
        pytest.skip("database below 0210")
    for table in (
        "roles",
        "permissions",
        "role_permissions",
        "membership_roles",
        "project_memberships",
        "site_memberships",
    ):
        cols = await _columns(engine, table)
        assert "created_at" in cols, f"{table} missing created_at"


async def test_0210_external_identities_has_created_at(engine) -> None:
    """G2: external_identities gains created_at."""
    if await _db_rev(engine) < "0210":
        pytest.skip("database below 0210")
    cols = await _columns(engine, "external_identities")
    assert "created_at" in cols


async def test_0210_context_tables_have_updated_at(engine) -> None:
    """G3: context_* tables gain updated_at."""
    if await _db_rev(engine) < "0210":
        pytest.skip("database below 0210")
    for table in (
        "context_organizations",
        "context_users",
        "context_projects",
        "context_sites",
    ):
        cols = await _columns(engine, table)
        assert "updated_at" in cols, f"{table} missing updated_at"


async def test_0210_inbound_messages_table_exists(engine) -> None:
    """G4: inbound_messages table is created."""
    if await _db_rev(engine) < "0210":
        pytest.skip("database below 0210")
    from sqlalchemy import text

    expected_cols = {
        "id", "correlation_id", "sender_wa_id", "message_type",
        "raw_payload", "normalized_message", "body_text", "media_object_key",
        "dedup_key", "received_at", "processed_at", "processing_status",
        "error_code",
    }
    cols = await _columns(engine, "inbound_messages")
    assert expected_cols <= cols


async def test_0210_journey_traces_table_exists(engine) -> None:
    """G5: journey_traces table is created."""
    if await _db_rev(engine) < "0210":
        pytest.skip("database below 0210")
    expected_cols = {
        "id", "correlation_id", "stage", "stage_payload",
        "duration_ms", "succeeded", "error_code", "error_message",
        "created_at",
    }
    cols = await _columns(engine, "journey_traces")
    assert expected_cols <= cols


def test_0210_migration_chain_links_to_0200():
    """The migration's down_revision must be 0200."""
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "0210_schema_add_audit_columns_and_message_log.py"
    )
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "0210"' in source
    assert 'down_revision = "0200"' in source
