"""Deterministic in-memory fakes for the M4 ports.

These power the default test lane (no live PostgreSQL / Redis). They enforce the
same tenant-isolation invariants as the real adapters: every project/site lookup
is scoped by ``(organization_id, user_id)`` and never leaks across tenants.

``FakeActiveContextStore`` emulates TTL/expiry with an injectable clock — the
real ``FakeRedis`` has no TTL emulation, so active-context expiry is modeled here
deterministically and (in the Redis adapter) enforced by an ``expires_at`` check.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

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


def _now() -> datetime:
    return datetime.now(UTC)


class FakeExternalIdentityRepository:
    def __init__(
        self,
        identities: list[ExternalIdentity] | None = None,
        users: list[User] | None = None,
    ) -> None:
        self._identities = {(i.provider, i.external_subject): i for i in (identities or [])}
        self._users = {u.user_id: u for u in (users or [])}

    async def find_identity(
        self, *, provider: str, external_subject: str
    ) -> ExternalIdentity | None:
        return self._identities.get((provider, external_subject))

    async def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)


class FakeMembershipRepository:
    def __init__(
        self,
        organizations: list[Organization] | None = None,
        memberships: list[Membership] | None = None,
    ) -> None:
        self._orgs = {o.organization_id: o for o in (organizations or [])}
        self._memberships = list(memberships or [])

    async def get_organization(self, organization_id: str) -> Organization | None:
        return self._orgs.get(organization_id)

    async def list_active_memberships(self, user_id: str) -> list[Membership]:
        out = []
        for m in self._memberships:
            if m.user_id != user_id or not m.is_active:
                continue
            org = self._orgs.get(m.organization_id)
            if org is not None and org.is_active:
                out.append(m)
        return out


class FakeRolePermissionRepository:
    def __init__(
        self,
        membership_roles: dict[str, list[str]] | None = None,
        membership_permissions: dict[str, list[str]] | None = None,
    ) -> None:
        self._roles = membership_roles or {}
        self._permissions = membership_permissions or {}

    async def role_ids_for_membership(self, membership_id: str) -> list[str]:
        return list(self._roles.get(membership_id, []))

    async def permissions_for_membership(self, membership_id: str) -> list[str]:
        # Deterministic order, de-duplicated.
        seen: dict[str, None] = {}
        for p in self._permissions.get(membership_id, []):
            seen.setdefault(p, None)
        return list(seen)


class _AuthorizedStore:
    """Shared authorization index used by the fake project/site repos."""

    def __init__(
        self,
        projects: list[Project],
        sites: list[Site],
        project_access: dict[str, set[str]],  # user_id -> {project_id}
        site_access: dict[str, set[str]] | None = None,  # user_id -> {site_id}
    ) -> None:
        self.projects = {p.project_id: p for p in projects}
        self.sites = {s.site_id: s for s in sites}
        self.project_access = project_access
        # If site access is not given, a user inherits every site of an
        # authorized project (common "project-level" membership case).
        self.site_access = site_access

    def user_project_ids(self, user_id: str) -> set[str]:
        return set(self.project_access.get(user_id, set()))

    def user_can_project(self, organization_id: str, user_id: str, project_id: str) -> bool:
        p = self.projects.get(project_id)
        if p is None or not p.is_active or p.organization_id != organization_id:
            return False
        return project_id in self.user_project_ids(user_id)

    def user_can_site(self, organization_id: str, user_id: str, site: Site) -> bool:
        if not site.is_active or site.organization_id != organization_id:
            return False
        if self.site_access is not None and user_id in self.site_access:
            return site.site_id in self.site_access[user_id]
        # Inherit from project-level authorization.
        return self.user_can_project(organization_id, user_id, site.project_id)


class FakeProjectRepository:
    def __init__(self, store: _AuthorizedStore) -> None:
        self._store = store

    async def get_authorized_project(
        self, *, organization_id: str, user_id: str, project_id: str
    ) -> Project | None:
        if self._store.user_can_project(organization_id, user_id, project_id):
            return self._store.projects[project_id]
        return None

    async def find_authorized_projects_by_name(
        self, *, organization_id: str, user_id: str, name: str
    ) -> list[Project]:
        needle = name.strip().casefold()
        out = []
        for pid in self._store.user_project_ids(user_id):
            p = self._store.projects.get(pid)
            if (
                p is not None
                and p.is_active
                and p.organization_id == organization_id
                and p.name.strip().casefold() == needle
            ):
                out.append(p)
        return sorted(out, key=lambda p: p.project_id)

    async def list_authorized_projects(
        self, *, organization_id: str, user_id: str
    ) -> list[Project]:
        out = [
            self._store.projects[pid]
            for pid in self._store.user_project_ids(user_id)
            if self._store.user_can_project(organization_id, user_id, pid)
        ]
        return sorted(out, key=lambda p: p.project_id)

    async def get_project_in_org(
        self, *, organization_id: str, project_id: str
    ) -> Project | None:
        p = self._store.projects.get(project_id)
        if p is not None and p.is_active and p.organization_id == organization_id:
            return p
        return None


class FakeSiteRepository:
    def __init__(self, store: _AuthorizedStore) -> None:
        self._store = store

    async def get_authorized_site(
        self, *, organization_id: str, user_id: str, site_id: str
    ) -> Site | None:
        site = self._store.sites.get(site_id)
        if site is not None and self._store.user_can_site(organization_id, user_id, site):
            return site
        return None

    async def find_authorized_sites_by_name(
        self, *, organization_id: str, user_id: str, name: str, project_id: str | None = None
    ) -> list[Site]:
        needle = name.strip().casefold()
        out = []
        for site in self._store.sites.values():
            if site.name.strip().casefold() != needle:
                continue
            if project_id is not None and site.project_id != project_id:
                continue
            if self._store.user_can_site(organization_id, user_id, site):
                out.append(site)
        return sorted(out, key=lambda s: s.site_id)

    async def get_site_in_org(
        self, *, organization_id: str, site_id: str
    ) -> Site | None:
        s = self._store.sites.get(site_id)
        if s is not None and s.is_active and s.organization_id == organization_id:
            return s
        return None


class FakeContextPreferenceRepository:
    def __init__(self, preferences: list[ContextPreferences] | None = None) -> None:
        self._prefs = {(p.organization_id, p.user_id): p for p in (preferences or [])}

    async def get_preferences(
        self, *, organization_id: str, user_id: str
    ) -> ContextPreferences | None:
        return self._prefs.get((organization_id, user_id))


class FakeActiveContextStore:
    """In-memory active context with deterministic TTL/expiry via an injected clock."""

    def __init__(self, *, clock: Callable[[], datetime] = _now) -> None:
        self._clock = clock
        self._store: dict[tuple[str, str], ActiveContext] = {}

    async def get_active_context(
        self, *, organization_id: str, user_id: str
    ) -> ActiveContext | None:
        ctx = self._store.get((organization_id, user_id))
        if ctx is None:
            return None
        if datetime.fromisoformat(ctx.expires_at) <= self._clock():
            # Expired: behave like Redis TTL eviction.
            self._store.pop((organization_id, user_id), None)
            return None
        return ctx

    async def set_active_context(
        self,
        *,
        organization_id: str,
        user_id: str,
        project_id: str | None,
        site_id: str | None,
        ttl_seconds: int,
    ) -> ActiveContext:
        now = self._clock()
        ctx = ActiveContext(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            site_id=site_id,
            selected_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
            context_version=1,
        )
        self._store[(organization_id, user_id)] = ctx
        return ctx

    async def clear_active_context(self, *, organization_id: str, user_id: str) -> None:
        self._store.pop((organization_id, user_id), None)


class FakeReplyContextProvider:
    def __init__(self, mapping: dict[str, tuple[str | None, str | None]] | None = None) -> None:
        # replied_to_message_id -> (project_id, site_id)
        self._mapping = mapping or {}

    async def context_for_reply(
        self, *, organization_id: str, replied_to_message_id: str
    ) -> tuple[str | None, str | None] | None:
        return self._mapping.get(replied_to_message_id)


class FakeWorkflowContextProvider:
    """Stand-in for the M5 workflow runtime (not implemented in M4)."""

    def __init__(self, mapping: dict[tuple[str, str], tuple[str | None, str | None]] | None = None) -> None:
        self._mapping = mapping or {}

    async def active_workflow_context(
        self, *, organization_id: str, user_id: str
    ) -> tuple[str | None, str | None] | None:
        return self._mapping.get((organization_id, user_id))
