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
    location: str | None = None
    code: str | None = None
    status: str | None = None
    progress: int | None = None
    open_issues: int | None = None


@dataclass(frozen=True, slots=True)
class SiteRef:
    id: str
    name: str
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class SenderContext:
    """The authoritative context resolved for a WhatsApp sender."""

    user_id: str
    full_name: str
    role: str
    organization_id: str | None
    org_name: str | None
    org_active: bool
    projects: list[ProjectRef] = field(default_factory=list)
    sites: list[SiteRef] = field(default_factory=list)


async def resolve_sender(engine, wa_id: str) -> SenderContext | None:
    """Resolve the sender from their WhatsApp id, or ``None`` if unregistered.

    A user record with ``organization_id IS NULL`` is still resolved (so the
    caller can give a distinct "no organization" message rather than silently
    treating them as unregistered).

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

        project_rows: list = []
        site_rows: list = []

        if org_id is not None:
            project_rows = (
                await conn.execute(
                    text(
                        "SELECT id, name, location, code, status, progress, open_issues "
                        "FROM projects "
                        "WHERE organization_id = :org ORDER BY name"
                    ),
                    {"org": str(org_id)},
                )
            ).mappings().all()

            # Sites live only in the M4 context_ table today (absent from the
            # control-plane). Query defensively so the reply includes them if
            # the table ever gets populated, without crashing otherwise.
            try:
                site_rows = (
                    await conn.execute(
                        text(
                            "SELECT id, name, project_id FROM context_sites "
                            "WHERE organization_id = :org ORDER BY name"
                        ),
                        {"org": str(org_id)},
                    )
                ).mappings().all()
            except Exception:
                site_rows = []

    return SenderContext(
        user_id=str(row["id"]),
        full_name=row["full_name"],
        role=str(row["role"]),
        organization_id=str(org_id) if org_id is not None else None,
        org_name=row["org_name"],
        org_active=(row["org_status"] == _ORG_ACTIVE) if row["org_status"] is not None else False,
        projects=[
            ProjectRef(
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
        sites=[SiteRef(id=str(s["id"]), name=s["name"], project_id=str(s["project_id"]) if s.get("project_id") else None) for s in site_rows],
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

NO_ORG_MESSAGE = (
    "👋 Hi {name}! You have a Mesiri account, but you're not part of any "
    "organization yet.\n\n"
    "Please ask your administrator to add you to an organization, then message again."
)

ORG_SUSPENDED_MESSAGE = (
    "⚠️ Your organization's Mesiri account is not active right now. "
    "Please contact your administrator."
)

# A small status emoji map so the whoami reply reads at a glance.
_STATUS_EMOJI = {
    "on_track": "🟢",
    "at_risk": "🟡",
    "critical": "🔴",
}


def _role_label(role: str) -> str:
    """Pretty-print a role enum value (ADMIN -> Admin)."""
    if not role:
        return "—"
    return role.replace("_", " ").title()


def context_header(ctx: SenderContext, project: ProjectRef | None) -> str:
    """A short identity/context banner prepended to the assistant's reply."""
    line = f"👤 {ctx.full_name} · 🏢 {ctx.org_name}"
    if project is not None:
        line += f" · 🏗 {project.name}"
    elif len(ctx.projects) > 1:
        line += " · 🏗 (project unspecified)"
    return line


def whoami_reply(ctx: SenderContext) -> str:
    """Render a full whoami summary: role, org, projects (with details), sites.

    This is the testing/debug回复 path: any inbound message from a registered,
    active-org user gets this back so we can verify identity resolution end to
    end against the live DB. It will be replaced by real understanding-driven
    replies once the Interaction layer (M7) lands.
    """
    lines: list[str] = []
    lines.append("*Mesiri — whoami*")
    lines.append("")
    lines.append(f"👤 Name: {ctx.full_name}")
    lines.append(f"🔑 Role: {_role_label(ctx.role)}")
    lines.append(f"🏢 Organization: {ctx.org_name}")

    # Projects
    if ctx.projects:
        lines.append("")
        lines.append(f"🏗 Projects ({len(ctx.projects)}):")
        for p in ctx.projects:
            emoji = _STATUS_EMOJI.get((p.status or "").lower(), "▪️")
            detail_parts: list[str] = []
            if p.location:
                detail_parts.append(f"📍 {p.location}")
            if p.code:
                detail_parts.append(f"🏷 {p.code}")
            if p.status:
                detail_parts.append(f"{emoji} {p.status.replace('_', ' ')}")
            if p.progress is not None:
                detail_parts.append(f"📈 {p.progress}%")
            if p.open_issues:
                detail_parts.append(f"⚠️ {p.open_issues} open")
            detail = " · ".join(detail_parts) if detail_parts else "—"
            lines.append(f"   • {p.name} — {detail}")
    else:
        lines.append("")
        lines.append("🏗 Projects: none assigned to your organization yet")

    # Sites (only the M4 context_sites table exists and is likely empty in prod)
    if ctx.sites:
        lines.append("")
        lines.append(f"📍 Sites ({len(ctx.sites)}):")
        for s in ctx.sites:
            lines.append(f"   • {s.name}")
    # Intentionally no "none" line for sites: the table is almost always empty
    # today, and listing "Sites: none" would be noise on every reply.

    lines.append("")
    lines.append("_(this is a test whoami reply — will be replaced by real understanding replies)_")
    return "\n".join(lines)
