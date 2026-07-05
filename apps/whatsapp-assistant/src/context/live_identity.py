"""Live WhatsApp sender identity + context resolution (control-plane tables).

Answers, for an inbound WhatsApp message: *who is this, do they belong to an
active organization, and which project does this belong to?* — reading the same
control-plane ``users`` / ``organizations`` / ``projects`` tables the mobile app
manages (so a number added on the Team page is immediately recognised).

This is the pragmatic bridge that makes identity checking work against real data
today. (The fuller M4 ``ContextResolver`` reads the dedicated ``context_*``
tables; those aren't populated in production, and WhatsApp numbers live in
``users.whatsapp_number``, so the live path resolves against that.)

Phone numbers are matched on **digits only**, so a number stored as
``+91 98765 43210`` matches Meta's ``wa_id`` ``919876543210``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# NOTE: sqlalchemy is imported lazily inside functions. Importing it at module
# top would pull in the stdlib ``platform`` module, which the repo's top-level
# ``platform/`` package shadows during test collection (see pyproject notes).

_ORG_ACTIVE = "Active"  # organizations.status value for an enabled tenant


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _get_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


@dataclass(frozen=True, slots=True)
class ProjectRef:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class SenderContext:
    """The authoritative context resolved for a WhatsApp sender."""

    user_id: str
    full_name: str
    role: str
    organization_id: str
    org_name: str
    org_active: bool
    projects: list[ProjectRef] = field(default_factory=list)


async def resolve_sender(engine, wa_id: str) -> SenderContext | None:
    """Resolve the sender from their WhatsApp id, or ``None`` if unregistered.

    Tenant-safe: everything is derived from the user's own ``organization_id``.
    """
    from sqlalchemy import text

    digits = _digits(wa_id)
    if not digits:
        return None

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT u.id, u.full_name, u.role, u.organization_id, "
                    "       o.name AS org_name, o.status AS org_status "
                    "FROM users u "
                    "JOIN organizations o ON o.id = u.organization_id "
                    "WHERE u.whatsapp_number IS NOT NULL "
                    "  AND regexp_replace(u.whatsapp_number, '\\D', '', 'g') = :d "
                    "LIMIT 1"
                ),
                {"d": digits},
            )
        ).mappings().first()

        if row is None:
            return None

        project_rows = (
            await conn.execute(
                text(
                    "SELECT id, name FROM projects "
                    "WHERE organization_id = :org ORDER BY name"
                ),
                {"org": str(row["organization_id"])},
            )
        ).mappings().all()

    return SenderContext(
        user_id=str(row["id"]),
        full_name=row["full_name"],
        role=row["role"],
        organization_id=str(row["organization_id"]),
        org_name=row["org_name"],
        org_active=(row["org_status"] == _ORG_ACTIVE),
        projects=[ProjectRef(id=str(p["id"]), name=p["name"]) for p in project_rows],
    )


# Field keys an UnderstandingResult may carry a project reference under.
_PROJECT_KEYS = ("project", "project_name", "project_reference")


def pick_project(understanding, projects: list[ProjectRef]) -> ProjectRef | None:
    """Deterministically choose the sender's project for this message.

    Precedence: an explicit project *named in the message* that matches an
    authorized project → that project; else if the user has exactly one project
    → that one; else unresolved (``None``) — never guess between several.
    """
    if not projects:
        return None

    by_name = {p.name.strip().casefold(): p for p in projects}
    candidates = getattr(understanding, "candidates", []) or []
    for cand in candidates:
        merged = {**getattr(cand, "fields", {}), **getattr(cand, "unknown_fields", {})}
        for key in _PROJECT_KEYS:
            val = merged.get(key)
            if val and str(val).strip().casefold() in by_name:
                return by_name[str(val).strip().casefold()]

    if len(projects) == 1:
        return projects[0]
    return None


# -- User-facing messages ----------------------------------------------------

UNREGISTERED_MESSAGE = (
    "👋 Hi! This number isn't registered on Mesiri yet.\n\n"
    "Please ask your administrator to add your WhatsApp number to your profile "
    "in the Mesiri app, then message again."
)

ORG_SUSPENDED_MESSAGE = (
    "⚠️ Your organization's Mesiri account is not active right now. "
    "Please contact your administrator."
)


def context_header(ctx: SenderContext, project: ProjectRef | None) -> str:
    """A short identity/context banner prepended to the assistant's reply."""
    line = f"👤 {ctx.full_name} · 🏢 {ctx.org_name}"
    if project is not None:
        line += f" · 🏗 {project.name}"
    elif len(ctx.projects) > 1:
        line += " · 🏗 (project unspecified)"
    return line
