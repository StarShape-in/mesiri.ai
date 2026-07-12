"""Authorization service for resolving request authorization context.

Responsible for loading the current user from the database, verifying their
status and organization membership, and resolving their access scope.
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from .context import (
    AccessPolicy,
    AuthorizationContext,
    ProjectAccessScope,
    SiteAccessScope,
    resolve_site_scope,
)

# Org-level roles that bypass explicit project_members rows entirely --
# the SQL-native equivalent of access_policy's "all_projects" mode. Mirrors
# the existing role.upper() == "ADMIN" bypass already used for action-level
# checks elsewhere (e.g. domains/projects/router.py's require_admin-style
# inline checks), now also applied at scope-resolution time.
_ORG_WIDE_ROLES = {"ADMIN"}


class AuthorizationService:
    """Service for resolving authorization context from JWT claims."""

    def __init__(self, conn: AsyncConnection):
        """Initialize with database connection."""
        self._conn = conn

        # Define users table structure inline (repository pattern applied later)
        self._users = sa.Table(
            "users",
            sa.MetaData(),
            sa.Column("id", sa.UUID(as_uuid=True)),
            sa.Column("organization_id", sa.UUID(as_uuid=True)),
            sa.Column("role", sa.String),
            sa.Column("status", sa.String),
            sa.Column("access_policy", sa.JSON),
        )

    async def resolve_from_jwt(
        self,
        user_id: UUID,
        org_id: UUID,
        role: str,
    ) -> AuthorizationContext:
        """Resolve authorization context from JWT claims.

        Loads current user from database and verifies:
        - User exists
        - User belongs to claimed organization
        - User status is active
        - Access policy is valid

        Returns:
            AuthorizationContext with resolved access scope

        Raises:
            HTTPException 401: User not found, disabled, or org mismatch
        """
        # Load current user from database
        result = await self._conn.execute(
            sa.select(
                self._users.c.id,
                self._users.c.organization_id,
                self._users.c.role,
                self._users.c.status,
                self._users.c.access_policy,
            ).where(self._users.c.id == user_id)
        )
        rows = result.fetchall()
        row = rows[0] if rows else None

        if row is None:
            raise HTTPException(status_code=401, detail="User not found or token invalid")

        # Verify organization consistency
        if row.organization_id != org_id:
            raise HTTPException(status_code=401, detail="Organization mismatch")

        # Verify user status
        user_status = row.status or "active"
        if user_status != "active":
            raise HTTPException(status_code=401, detail=f"User account is {user_status}")

        # access_policy is parsed only for GET /me backward compatibility --
        # it is no longer authoritative for scope resolution (see
        # project/site membership audit: this JSONB column and project_members
        # used to be two disconnected sources of truth; project_members +
        # site_members is now the only one consulted below).
        access_policy = AccessPolicy.from_db_json(row.access_policy)

        # Resolve project access scope from project_members (+ role bypass)
        project_scope = await self._resolve_project_scope(row.role, user_id, org_id)
        site_scopes = await self._resolve_site_scopes(project_scope, user_id, org_id)

        return AuthorizationContext(
            user_id=row.id,
            organization_id=row.organization_id,
            role=row.role,
            status=user_status,
            access_policy=access_policy,
            project_scope=project_scope,
            site_scopes=site_scopes,
        )

    async def _resolve_project_scope(
        self,
        role: str,
        user_id: UUID,
        org_id: UUID,
    ) -> ProjectAccessScope:
        """Resolve project access scope from project_members (+ org-wide role bypass).

        Rules:
        - An org-wide role (currently just ADMIN) grants access to every
          project in the organization, present and future -- the SQL-native
          equivalent of access_policy's old "all_projects" mode, without
          needing a project_members row per project per admin.
        - Otherwise: access is exactly the set of projects this user has an
          explicit project_members row for, scoped to this organization.
        - No project_members rows: zero projects (deny-by-default, same as
          the old empty custom_projects list).
        """
        if role.upper() in _ORG_WIDE_ROLES:
            return ProjectAccessScope(mode="all_projects", project_ids=set())

        rows = await self._conn.execute(
            sa.text(
                "SELECT pm.project_id FROM project_members pm "
                "JOIN projects p ON p.id = pm.project_id "
                "WHERE pm.user_id = :user_id AND p.organization_id = :org_id"
            ),
            {"user_id": user_id, "org_id": org_id},
        )
        project_ids = {r.project_id for r in rows.fetchall()}
        return ProjectAccessScope(mode="custom_projects", project_ids=project_ids)

    async def _resolve_site_scopes(
        self,
        project_scope: ProjectAccessScope,
        user_id: UUID,
        org_id: UUID,
    ) -> dict[UUID, SiteAccessScope]:
        """Resolve per-project site access scope for every project this user
        can reach, from project_members.site_access_mode + site_members.

        Precomputed upfront (rather than lazily per project_id) so
        AuthorizationContext.site_scope_for_project stays a pure, DB-free
        dataclass method -- matching how project_scope is already fully
        resolved before the context is constructed.
        """
        if project_scope.grants_all_org_projects:
            # Org-wide role bypass: every project, all sites -- mirrors the
            # old "all_projects implies all_sites for every project" rule.
            rows = await self._conn.execute(
                sa.text("SELECT id FROM projects WHERE organization_id = :org_id"),
                {"org_id": org_id},
            )
            return {
                r.id: SiteAccessScope(mode="all_sites", site_ids=set()) for r in rows.fetchall()
            }

        if not project_scope.project_ids:
            return {}

        member_rows = await self._conn.execute(
            sa.text(
                "SELECT project_id, site_access_mode FROM project_members "
                "WHERE user_id = :user_id AND project_id IN :project_ids"
            ).bindparams(sa.bindparam("project_ids", expanding=True)),
            {"user_id": user_id, "project_ids": list(project_scope.project_ids)},
        )
        site_scopes: dict[UUID, SiteAccessScope] = {}
        custom_site_project_ids: list[UUID] = []
        for r in member_rows.fetchall():
            if r.site_access_mode == "custom_sites":
                custom_site_project_ids.append(r.project_id)
            else:
                site_scopes[r.project_id] = SiteAccessScope(mode="all_sites", site_ids=set())

        if custom_site_project_ids:
            explicit_sites: dict[UUID, set[UUID]] = {pid: set() for pid in custom_site_project_ids}
            site_rows = await self._conn.execute(
                sa.text(
                    "SELECT s.project_id, sm.site_id FROM site_members sm "
                    "JOIN sites s ON s.id = sm.site_id "
                    "WHERE sm.user_id = :user_id AND s.project_id IN :project_ids"
                ).bindparams(sa.bindparam("project_ids", expanding=True)),
                {"user_id": user_id, "project_ids": custom_site_project_ids},
            )
            for r in site_rows.fetchall():
                explicit_sites[r.project_id].add(r.site_id)
            for pid, site_ids in explicit_sites.items():
                site_scopes[pid] = SiteAccessScope(mode="custom_sites", site_ids=site_ids)

        return site_scopes

    @staticmethod
    def _resolve_site_scope(access_policy: AccessPolicy, project_id: UUID) -> SiteAccessScope:
        """Resolve site access scope for a project from an access policy.

        Pure function of the already-parsed access_policy — no DB access is
        needed since siteAccess is nested inside the same JSON blob resolved
        by _resolve_project_scope. See context.resolve_site_scope for the
        deny-by-default rules.
        """
        return resolve_site_scope(access_policy, project_id)
