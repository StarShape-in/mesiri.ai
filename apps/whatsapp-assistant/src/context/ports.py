"""M4 context ports (interfaces).

Small, single-responsibility ports — never one giant ``ContextRepository``. Each
authoritative responsibility is explicit. Real implementations live behind the
infrastructure boundary (PostgreSQL / Redis adapters); deterministic fakes power
the default test lane. The resolver depends only on these Protocols.

Ambiguity is represented as *data*, not errors, at the repository boundary: a
name lookup returns a list of authorized matches and the resolver decides
0 -> unresolved, 1 -> resolved, >1 -> ambiguous.
"""

from __future__ import annotations

from typing import Protocol

from .models import (
    ActiveContext,
    ContextPreferences,
    ExternalIdentity,
    Membership,
    Organization,
    Project,
    Site,
    User,
)


class ExternalIdentityRepository(Protocol):
    async def find_identity(
        self, *, provider: str, external_subject: str
    ) -> ExternalIdentity | None: ...

    async def get_user(self, user_id: str) -> User | None: ...


class OrganizationMembershipRepository(Protocol):
    async def get_organization(self, organization_id: str) -> Organization | None: ...

    async def list_active_memberships(self, user_id: str) -> list[Membership]: ...


class RolePermissionRepository(Protocol):
    async def role_ids_for_membership(self, membership_id: str) -> list[str]: ...

    async def permissions_for_membership(self, membership_id: str) -> list[str]: ...


class ProjectRepository(Protocol):
    async def get_authorized_project(
        self, *, organization_id: str, user_id: str, project_id: str
    ) -> Project | None: ...

    async def find_authorized_projects_by_name(
        self, *, organization_id: str, user_id: str, name: str
    ) -> list[Project]: ...

    async def list_authorized_projects(
        self, *, organization_id: str, user_id: str
    ) -> list[Project]: ...

    async def get_project_in_org(
        self, *, organization_id: str, project_id: str
    ) -> Project | None:
        """Org-scoped existence check (ignores user authorization).

        Tenant-safe: a project belonging to another organization returns None.
        Used only to distinguish *access denied* (exists in my org, not assigned)
        from *not found*.
        """
        ...


class SiteRepository(Protocol):
    async def get_authorized_site(
        self, *, organization_id: str, user_id: str, site_id: str
    ) -> Site | None: ...

    async def find_authorized_sites_by_name(
        self, *, organization_id: str, user_id: str, name: str, project_id: str | None = None
    ) -> list[Site]: ...

    async def get_site_in_org(
        self, *, organization_id: str, site_id: str
    ) -> Site | None:
        """Org-scoped existence check (ignores user authorization). Tenant-safe."""
        ...


class ContextPreferenceRepository(Protocol):
    async def get_preferences(
        self, *, organization_id: str, user_id: str
    ) -> ContextPreferences | None: ...


class ActiveContextStore(Protocol):
    """Ephemeral active context (Redis). Never the source of authorization."""

    async def get_active_context(
        self, *, organization_id: str, user_id: str
    ) -> ActiveContext | None: ...

    async def set_active_context(
        self,
        *,
        organization_id: str,
        user_id: str,
        project_id: str | None,
        site_id: str | None,
        ttl_seconds: int,
    ) -> ActiveContext: ...

    async def clear_active_context(self, *, organization_id: str, user_id: str) -> None: ...


class ReplyContextProvider(Protocol):
    """Maps a replied-to message id to the context it was resolved under."""

    async def context_for_reply(
        self, *, organization_id: str, replied_to_message_id: str
    ) -> tuple[str | None, str | None] | None: ...


class WorkflowContextProvider(Protocol):
    """Active workflow context (owned by M5; represented behind a port in M4)."""

    async def active_workflow_context(
        self, *, organization_id: str, user_id: str
    ) -> tuple[str | None, str | None] | None: ...


class IdentityBridgeRepository(Protocol):
    async def canonical_organization_id(self, context_organization_id: str) -> str | None: ...

    async def canonical_user_id(self, context_user_id: str) -> str | None: ...

    async def canonical_project_id(self, context_project_id: str) -> str | None: ...

    async def canonical_site_id(self, context_site_id: str) -> str | None: ...
