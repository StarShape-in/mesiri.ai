"""Schema guard for migration 0361: tenant deletion must stay a pure cascade.

0361 replaced the ~90-line hand-ordered DELETE sequence in
apps/whatsapp-assistant/src/admin/router.delete_organization with a single
`DELETE FROM organizations WHERE id = :org_id`, by putting ON DELETE CASCADE
on every tenant-scoped table's path back to organizations.id. That guarantee
is only as good as the next migration remembering to extend it — which is
exactly what broke last time (the finance refactor in 0320-0340 added new
org-scoped tables and the *old* handler was never updated to clear them).

This test makes that drift loud instead of silent: it inspects the live
schema and fails if any table with an `organization_id` column FK'd straight
to `organizations` doesn't cascade, or if any of the known child tables that
have no organization_id of their own (and so only reach organizations
through another tenant-scoped table) loses its cascade path.

Deliberately out of scope, matching what delete_organization has always left
alone: the context_organizations-rooted subsystem (context_projects,
context_sites, context_users, organization_memberships, roles,
project_memberships, site_memberships, external_identities,
user_context_preferences) is a distinct tenant root this handler never
touched, and units_of_measure/unit_aliases are global catalogs, not
tenant-scoped.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings

pytestmark = pytest.mark.integration

# (table, local_column) -> the only FK that reaches this table down from
# organizations.id, for tables with no organization_id column of their own.
# Adding a new such table means adding both its ON DELETE CASCADE FK (in a
# migration) and an entry here — that pairing is the point of this test.
_CHILD_TABLES_WITHOUT_ORG_ID = {
    ("expense_attachments", "expense_id"),
    ("budget_allocations", "budget_id"),
    ("labour_attendance_entries", "attendance_id"),
    ("interactions", "user_id"),
}


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


async def _foreign_keys(engine: AsyncEngine, table: str) -> list[dict]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_foreign_keys(table)
        )


async def _tables(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())


async def test_every_organization_id_fk_to_organizations_cascades(engine: AsyncEngine):
    for table in await _tables(engine):
        for fk in await _foreign_keys(engine, table):
            # Only tenant-scoped tables' organization_id column is in scope here.
            # context_organizations.canonical_organization_id also FKs straight to
            # organizations (the identity bridge, migration 0190) but is a
            # different, intentional relationship for a table this handler never
            # touches (see module docstring) -- not a tenant-scoped data row, so
            # it's not asserted on.
            if fk["referred_table"] != "organizations" or fk["constrained_columns"] != [
                "organization_id"
            ]:
                continue
            assert fk["options"].get("ondelete") == "CASCADE", (
                f"{table}.organization_id references organizations but doesn't "
                "cascade on delete -- deleting a tenant will either 500 or leave "
                "orphaned rows in this table. Add ON DELETE CASCADE in a migration."
            )


async def test_known_child_tables_without_organization_id_still_cascade(engine: AsyncEngine):
    for table, local_column in _CHILD_TABLES_WITHOUT_ORG_ID:
        fks = await _foreign_keys(engine, table)
        matching = [fk for fk in fks if fk["constrained_columns"] == [local_column]]
        assert matching, f"{table}.{local_column}: expected FK not found"
        assert matching[0]["options"].get("ondelete") == "CASCADE", (
            f"{table}.{local_column} is the only path down from organizations for "
            "this table and must cascade, or deleting a tenant will orphan/violate "
            "on this table."
        )
