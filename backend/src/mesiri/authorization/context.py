"""Authorization context for request-scoped access control.

Encapsulates the authenticated user's identity, organization membership,
status, and resolved access scope for resources like projects and sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AccessPolicy:
    """User's access policy defining which resources they can access.

    Canonical semantics:
    - mode="all_projects": user has access to all projects in their organization
    - mode="custom_projects": user has access only to explicitly listed projects
    - projects: list of project access grants with optional site-level restrictions
    """

    mode: str  # "all_projects" | "custom_projects"
    projects: list[dict[str, Any]]  # List of {projectId, siteAccess: {mode, siteIds}}

    @classmethod
    def from_db_json(cls, policy_json: dict[str, Any] | None) -> AccessPolicy:
        """Parse access policy from database JSONB.

        Returns deny-by-default empty custom scope if policy is missing, null,
        malformed, or has unsupported mode.
        """
        if policy_json is None:
            # Deny by default: missing policy = empty custom scope
            return cls(mode="custom_projects", projects=[])

        mode = policy_json.get("mode")
        if mode not in ("all_projects", "custom_projects"):
            # Deny by default: unsupported mode = empty custom scope
            return cls(mode="custom_projects", projects=[])

        projects = policy_json.get("projects", [])
        if not isinstance(projects, list):
            # Deny by default: malformed projects = empty custom scope
            return cls(mode="custom_projects", projects=[])

        return cls(mode=mode, projects=projects)


@dataclass(frozen=True)
class ProjectAccessScope:
    """Resolved project access scope for the current request.

    Determines which projects the user can query/access.
    """

    mode: str  # "all_projects" | "custom_projects"
    project_ids: set[UUID]  # If custom_projects, explicit project UUIDs; if all, empty set

    @property
    def grants_all_org_projects(self) -> bool:
        """True if user has access to all projects in their organization."""
        return self.mode == "all_projects"

    @property
    def grants_no_projects(self) -> bool:
        """True if user has empty custom scope (zero projects accessible)."""
        return self.mode == "custom_projects" and len(self.project_ids) == 0


@dataclass(frozen=True)
class SiteAccessScope:
    """Resolved site access scope for a single project.

    Determines which sites within a given project the user can query/access.
    Unlike ProjectAccessScope, this is always resolved relative to one
    project_id — a user's site access can differ per project.
    """

    mode: str  # "all_sites" | "custom_sites"
    site_ids: set[UUID]  # If custom_sites, explicit site UUIDs; if all, empty set

    @property
    def grants_all_sites(self) -> bool:
        """True if user has access to all sites within the project."""
        return self.mode == "all_sites"

    @property
    def grants_no_sites(self) -> bool:
        """True if user has empty custom scope (zero sites accessible)."""
        return self.mode == "custom_sites" and len(self.site_ids) == 0


def resolve_site_scope(access_policy: AccessPolicy, project_id: UUID) -> SiteAccessScope:
    """Resolve site access scope for a specific project from an access policy.

    Rules (deny-by-default, mirrors AuthorizationService._resolve_project_scope):
    - The org-wide "all_projects" mode implies "all_sites" for every project,
      since no per-project siteAccess entries exist in that mode.
    - Under "custom_projects", each project grant carries its own siteAccess
      ({"mode": "all_sites"|"custom_sites", "siteIds": [...]}).
    - Missing/malformed siteAccess, or a project_id with no matching grant,
      resolves to an empty custom scope (zero sites accessible).
    """
    if access_policy.mode == "all_projects":
        return SiteAccessScope(mode="all_sites", site_ids=set())

    for grant in access_policy.projects:
        if not isinstance(grant, dict):
            continue
        grant_project_id = grant.get("projectId")
        if grant_project_id != str(project_id):
            continue

        site_access = grant.get("siteAccess")
        if not isinstance(site_access, dict):
            return SiteAccessScope(mode="custom_sites", site_ids=set())

        site_mode = site_access.get("mode")
        if site_mode not in ("all_sites", "custom_sites"):
            return SiteAccessScope(mode="custom_sites", site_ids=set())

        if site_mode == "all_sites":
            return SiteAccessScope(mode="all_sites", site_ids=set())

        site_ids_raw = site_access.get("siteIds", [])
        if not isinstance(site_ids_raw, list):
            return SiteAccessScope(mode="custom_sites", site_ids=set())

        site_ids: set[UUID] = set()
        for site_id_str in site_ids_raw:
            try:
                site_ids.add(UUID(site_id_str))
            except (ValueError, TypeError):
                pass
        return SiteAccessScope(mode="custom_sites", site_ids=site_ids)

    # No grant found for this project: deny by default.
    return SiteAccessScope(mode="custom_sites", site_ids=set())


@dataclass(frozen=True)
class AuthorizationContext:
    """Request-scoped authorization context.

    Contains the authenticated user's identity, organization, status,
    and resolved access scope. Created once per request after JWT validation
    and user verification.
    """

    user_id: UUID
    organization_id: UUID
    role: str
    status: str
    access_policy: AccessPolicy
    project_scope: ProjectAccessScope

    @property
    def is_active(self) -> bool:
        """True if user status permits access."""
        return self.status == "active"

    def site_scope_for_project(self, project_id: UUID) -> SiteAccessScope:
        """Resolve this user's site access scope for a specific project."""
        return resolve_site_scope(self.access_policy, project_id)
