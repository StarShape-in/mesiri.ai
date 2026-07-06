"""PostgreSQL implementation of the ActorReader port.

THIS IS THE ONLY FILE IN THE ASSISTANT THAT IS ALLOWED TO:
  - know about the users, organizations, projects, or sites tables
  - write JOIN conditions against the backend schema
  - hold a raw SQLAlchemy engine / connection
  - apply raw tenant-filtering SQL

If the backend schema changes, change this file. Nothing else in the assistant
should need to change.
"""

from __future__ import annotations

import os
import re

from backend.ports import ActorIdentity, ActorReader, ProjectSummary, SiteSummary

_ORG_ACTIVE_STATUS = "Active"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _build_engine():
    # SQLAlchemy imported lazily to avoid the platform/ shadow-package issue
    # during test collection (see pyproject notes in the repo root).
    from sqlalchemy.ext.asyncio import create_async_engine

    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


class PostgresActorReader:
    """Satisfies the ActorReader Protocol by querying the backend control-plane.

    Resolves a WhatsApp sender to their ActorIdentity in a single round-trip
    (user + org JOIN) followed by two additional queries for projects and sites.
    All SQL is tenant-scoped on organization_id.

    Lifecycle: create once at process startup; the underlying engine maintains
    a connection pool for the process lifetime.
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or _build_engine()

    async def resolve_by_whatsapp_id(self, wa_id: str) -> ActorIdentity | None:
        from sqlalchemy import text

        digits = _digits(wa_id)
        if not digits:
            return None

        async with self._engine.connect() as conn:
            # ----------------------------------------------------------------
            # 1. Resolve the user + organization in one query.
            # ----------------------------------------------------------------
            row = (
                await conn.execute(
                    text(
                        "SELECT u.id, u.full_name, u.role, u.organization_id,"
                        "       o.name AS org_name, o.status AS org_status "
                        "FROM users u "
                        "LEFT JOIN organizations o ON o.id = u.organization_id "
                        "WHERE u.whatsapp_number IS NOT NULL "
                        "  AND regexp_replace(u.whatsapp_number, '\\D', '', 'g') = :d "
                        "LIMIT 1"
                    ),
                    {"d": digits},
                )
            ).mappings().first()

            if row is None:
                return None

            org_id = row["organization_id"]

            # ----------------------------------------------------------------
            # 2. Projects for this organization.
            # ----------------------------------------------------------------
            project_rows: list = []
            site_rows: list = []

            if org_id is not None:
                project_rows = (
                    await conn.execute(
                        text(
                            "SELECT id, name, location, code, status,"
                            "       progress, open_issues "
                            "FROM projects "
                            "WHERE organization_id = :org "
                            "ORDER BY name"
                        ),
                        {"org": str(org_id)},
                    )
                ).mappings().all()

                # ------------------------------------------------------------
                # 3. Sites from the control-plane sites table.
                #    Falls back gracefully if the migration hasn't run yet.
                # ------------------------------------------------------------
                try:
                    site_rows = (
                        await conn.execute(
                            text(
                                "SELECT id, name, project_id "
                                "FROM sites "
                                "WHERE organization_id = :org "
                                "  AND status = 'active' "
                                "ORDER BY name"
                            ),
                            {"org": str(org_id)},
                        )
                    ).mappings().all()
                except Exception:  # noqa: BLE001 — table may not exist yet
                    site_rows = []

        return ActorIdentity(
            user_id=str(row["id"]),
            full_name=row["full_name"],
            role=str(row["role"]),
            organization_id=str(org_id) if org_id is not None else None,
            org_name=row["org_name"],
            org_active=(row["org_status"] == _ORG_ACTIVE_STATUS)
            if row["org_status"] is not None
            else False,
            projects=[
                ProjectSummary(
                    id=str(p["id"]),
                    name=p["name"],
                    location=p.get("location"),
                    code=p.get("code"),
                    status=p.get("status"),
                    progress=p.get("progress"),
                    open_issues=p.get("open_issues"),
                )
                for p in project_rows
            ],
            sites=[
                SiteSummary(
                    id=str(s["id"]),
                    name=s["name"],
                    project_id=str(s["project_id"]) if s.get("project_id") else None,
                )
                for s in site_rows
            ],
        )
