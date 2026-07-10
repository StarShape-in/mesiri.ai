"""PostgreSQL-backed implementations of the M4 context ports.

Authoritative context lives here. Every project/site query is tenant-scoped by
``organization_id`` (and authorization-scoped by ``user_id`` for the
``get_authorized_*`` / ``find_authorized_*`` methods) so no query can ever leak
across organizations. Raw driver exceptions are mapped to the shared error
contract by the M1 infrastructure boundary (``map_postgres_error``).

SQL lives ONLY in this module — the resolver/orchestration never sees it. These
adapters take a SQLAlchemy ``AsyncEngine`` directly so M4 stays self-contained
without modifying the M1 ``PostgresDatabase`` facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mesiri.infrastructure.errors import map_postgres_error

from .models import (
    ContextPreferences,
    ExternalIdentity,
    Membership,
    Organization,
    Project,
    Site,
    User,
)

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncEngine


class _EngineMixin:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _rows(self, sql: str, params: dict[str, Any]) -> list[Any]:
        from sqlalchemy import text

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                return list(result.mappings().all())
        except Exception as exc:  # noqa: BLE001
            raise map_postgres_error(exc) from exc

    async def _row(self, sql: str, params: dict[str, Any]) -> Any | None:
        rows = await self._rows(sql, params)
        return rows[0] if rows else None


class PostgresExternalIdentityRepository(_EngineMixin):
    async def find_identity(
        self, *, provider: str, external_subject: str
    ) -> ExternalIdentity | None:
        row = await self._row(
            "SELECT provider, external_subject, user_id FROM external_identities "
            "WHERE provider = :p AND external_subject = :s",
            {"p": provider, "s": external_subject},
        )
        if row is None:
            return None
        return ExternalIdentity(row["provider"], row["external_subject"], row["user_id"])

    async def get_user(self, user_id: str) -> User | None:
        row = await self._row(
            "SELECT id, is_active, locale, timezone FROM context_users WHERE id = :id",
            {"id": user_id},
        )
        if row is None:
            return None
        return User(row["id"], bool(row["is_active"]), row["locale"], row["timezone"])


class PostgresMembershipRepository(_EngineMixin):
    async def get_organization(self, organization_id: str) -> Organization | None:
        row = await self._row(
            "SELECT id, is_active FROM context_organizations WHERE id = :id",
            {"id": organization_id},
        )
        if row is None:
            return None
        return Organization(row["id"], bool(row["is_active"]))

    async def list_active_memberships(self, user_id: str) -> list[Membership]:
        rows = await self._rows(
            "SELECT m.id, m.organization_id, m.user_id, m.is_active "
            "FROM organization_memberships m "
            "JOIN context_organizations o ON o.id = m.organization_id "
            "WHERE m.user_id = :u AND m.is_active = true AND o.is_active = true "
            "ORDER BY m.organization_id",
            {"u": user_id},
        )
        return [
            Membership(r["id"], r["organization_id"], r["user_id"], bool(r["is_active"]))
            for r in rows
        ]


class PostgresRolePermissionRepository(_EngineMixin):
    async def role_ids_for_membership(self, membership_id: str) -> list[str]:
        rows = await self._rows(
            "SELECT role_id FROM membership_roles WHERE membership_id = :m ORDER BY role_id",
            {"m": membership_id},
        )
        return [r["role_id"] for r in rows]

    async def permissions_for_membership(self, membership_id: str) -> list[str]:
        rows = await self._rows(
            "SELECT DISTINCT p.code FROM membership_roles mr "
            "JOIN role_permissions rp ON rp.role_id = mr.role_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE mr.membership_id = :m ORDER BY p.code",
            {"m": membership_id},
        )
        return [r["code"] for r in rows]


def _project(r: Any) -> Project:
    return Project(r["id"], r["organization_id"], r["name"], bool(r["is_active"]))


def _site(r: Any) -> Site:
    return Site(r["id"], r["project_id"], r["organization_id"], r["name"], bool(r["is_active"]))


# A user is authorized for a project via a direct project_membership OR (site
# membership implies its project). Tenant-scoped by organization_id everywhere.
_AUTHORIZED_PROJECT_IDS = (
    "SELECT p.id FROM context_projects p WHERE p.organization_id = :org AND p.is_active = true AND ("
    "  p.id IN (SELECT project_id FROM project_memberships WHERE user_id = :u)"
    "  OR p.id IN (SELECT s.project_id FROM site_memberships sm "
    "              JOIN context_sites s ON s.id = sm.site_id WHERE sm.user_id = :u)"
    ")"
)


class PostgresProjectRepository(_EngineMixin):
    async def get_authorized_project(
        self, *, organization_id: str, user_id: str, project_id: str
    ) -> Project | None:
        row = await self._row(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE id = :pid AND id IN ({_AUTHORIZED_PROJECT_IDS})",
            {"pid": project_id, "org": organization_id, "u": user_id},
        )
        return _project(row) if row else None

    async def find_authorized_projects_by_name(
        self, *, organization_id: str, user_id: str, name: str
    ) -> list[Project]:
        rows = await self._rows(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE lower(name) = lower(:name) AND id IN ({_AUTHORIZED_PROJECT_IDS}) ORDER BY id",
            {"name": name.strip(), "org": organization_id, "u": user_id},
        )
        return [_project(r) for r in rows]

    async def list_authorized_projects(
        self, *, organization_id: str, user_id: str
    ) -> list[Project]:
        rows = await self._rows(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE id IN ({_AUTHORIZED_PROJECT_IDS}) ORDER BY id",
            {"org": organization_id, "u": user_id},
        )
        return [_project(r) for r in rows]

    async def get_project_in_org(self, *, organization_id: str, project_id: str) -> Project | None:
        row = await self._row(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            "WHERE id = :pid AND organization_id = :org AND is_active = true",
            {"pid": project_id, "org": organization_id},
        )
        return _project(row) if row else None


class PostgresSiteRepository(_EngineMixin):
    async def get_authorized_site(
        self, *, organization_id: str, user_id: str, site_id: str
    ) -> Site | None:
        row = await self._row(
            "SELECT s.id, s.project_id, s.organization_id, s.name, s.is_active FROM context_sites s "
            "WHERE s.id = :sid AND s.organization_id = :org AND s.is_active = true AND ("
            "  s.id IN (SELECT site_id FROM site_memberships WHERE user_id = :u)"
            f"  OR s.project_id IN ({_AUTHORIZED_PROJECT_IDS})"
            ")",
            {"sid": site_id, "org": organization_id, "u": user_id},
        )
        return _site(row) if row else None

    async def find_authorized_sites_by_name(
        self, *, organization_id: str, user_id: str, name: str, project_id: str | None = None
    ) -> list[Site]:
        clause = ""
        params: dict[str, Any] = {"name": name.strip(), "org": organization_id, "u": user_id}
        if project_id is not None:
            clause = " AND s.project_id = :pid"
            params["pid"] = project_id
        rows = await self._rows(
            "SELECT s.id, s.project_id, s.organization_id, s.name, s.is_active FROM context_sites s "
            "WHERE lower(s.name) = lower(:name) AND s.organization_id = :org "
            "AND s.is_active = true" + clause + " AND ("
            "  s.id IN (SELECT site_id FROM site_memberships WHERE user_id = :u)"
            f"  OR s.project_id IN ({_AUTHORIZED_PROJECT_IDS})"
            ") ORDER BY s.id",
            params,
        )
        return [_site(r) for r in rows]

    async def get_site_in_org(self, *, organization_id: str, site_id: str) -> Site | None:
        row = await self._row(
            "SELECT id, project_id, organization_id, name, is_active FROM context_sites "
            "WHERE id = :sid AND organization_id = :org AND is_active = true",
            {"sid": site_id, "org": organization_id},
        )
        return _site(row) if row else None


class PostgresContextPreferenceRepository(_EngineMixin):
    async def get_preferences(
        self, *, organization_id: str, user_id: str
    ) -> ContextPreferences | None:
        row = await self._row(
            "SELECT organization_id, user_id, default_project_id, default_site_id, locale, timezone "
            "FROM user_context_preferences WHERE organization_id = :org AND user_id = :u",
            {"org": organization_id, "u": user_id},
        )
        if row is None:
            return None
        return ContextPreferences(
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            default_project_id=row["default_project_id"],
            default_site_id=row["default_site_id"],
            locale=row["locale"],
            timezone=row["timezone"],
        )
