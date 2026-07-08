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
