"""Seed demo projects for organizations that have none.

Idempotent: an org that already has >=1 project is skipped, so re-running never
duplicates. Inserts into the control-plane ``projects`` table (the same table the
mobile app's live /projects endpoint reads), scoped per organization.

Usage:
    python scripts/seed_projects.py                 # seed every org with 0 projects
    python scripts/seed_projects.py "Superman"      # seed only orgs whose name matches

Requires the DB env vars (same as the app):
    MESIRI_POSTGRES__HOST / __PORT / __USER / __PASSWORD / __DATABASE
Run `make migrate` first so the projects table exists.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

# Demo projects seeded per organization (name, location, status, progress, open_issues).
_DEMO_PROJECTS = [
    ("Skyline Towers", "North Zone", "critical", 68, 3),
    ("Green Valley", "East Zone", "at_risk", 42, 1),
    ("Metro Heights", "South Zone", "on_track", 89, 0),
]

_metadata = sa.MetaData()
organizations_table = sa.Table(
    "organizations", _metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("name", sa.String),
)
projects_table = sa.Table(
    "projects", _metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("organization_id", sa.UUID),
    sa.Column("name", sa.String),
    sa.Column("location", sa.String),
    sa.Column("status", sa.String),
    sa.Column("progress", sa.Integer),
    sa.Column("open_issues", sa.Integer),
)


def _engine():
    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


async def run(name_filter: str | None) -> int:
    engine = _engine()
    seeded = 0
    async with engine.begin() as conn:
        query = sa.select(organizations_table)
        if name_filter:
            query = query.where(organizations_table.c.name.ilike(f"%{name_filter}%"))
        orgs = (await conn.execute(query)).fetchall()

        if not orgs:
            print(f"No organizations found{f' matching {name_filter!r}' if name_filter else ''}.")
            return 0

        for org in orgs:
            existing = (
                await conn.execute(
                    sa.select(sa.func.count())
                    .select_from(projects_table)
                    .where(projects_table.c.organization_id == org.id)
                )
            ).scalar_one()
            if existing:
                print(f"[skip] {org.name} already has {existing} project(s)")
                continue

            for pname, location, status, progress, issues in _DEMO_PROJECTS:
                await conn.execute(
                    projects_table.insert().values(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        name=pname,
                        location=location,
                        status=status,
                        progress=progress,
                        open_issues=issues,
                    )
                )
            seeded += 1
            print(f"[seed] {org.name}: added {len(_DEMO_PROJECTS)} projects")

    await engine.dispose()
    print(f"\nDone. Seeded {seeded} organization(s).")
    return 0


def main() -> int:
    name_filter = sys.argv[1] if len(sys.argv) > 1 else None
    return asyncio.run(run(name_filter))


if __name__ == "__main__":
    sys.exit(main())
