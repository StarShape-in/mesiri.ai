"""Active-context selection application service (M4).

Implements the *capability* to change a user's ephemeral active context (e.g. a
director messaging "switch to Marina Tower"). It authorizes the target against
PostgreSQL, then writes the ephemeral selection to Redis via the store port.

This is deliberately NOT workflow routing (M5). It exposes a directly testable
application method; how a switch *intent* reaches it is a downstream concern.
"""

from __future__ import annotations

from mesiri.observability import tracing
from mesiri.observability.logging import get_logger
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.common.result import Result

from . import errors
from .models import ActiveContext
from .ports import ActiveContextStore, ProjectRepository, SiteRepository

_log = get_logger("mesiri.context")

DEFAULT_ACTIVE_CONTEXT_TTL_SECONDS = 12 * 60 * 60  # 12h


class ContextSwitchService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        sites: SiteRepository,
        active_context: ActiveContextStore,
        ttl_seconds: int = DEFAULT_ACTIVE_CONTEXT_TTL_SECONDS,
    ) -> None:
        self._projects = projects
        self._sites = sites
        self._active = active_context
        self._ttl = ttl_seconds

    async def select_active_context(
        self,
        *,
        organization_id: str,
        user_id: str,
        project_id: str,
        site_id: str | None = None,
    ) -> Result[ActiveContext]:
        """Authorize then persist the user's active context. Never trusts input."""
        try:
            active = await self._select(organization_id, user_id, project_id, site_id)
        except MesiriError as err:
            _log.error("context.active_context_set", error=err, result_status="rejected")
            return Result.err(err)
        _log.info(
            "context.active_context_set",
            organization_id=organization_id,
            user_id=user_id,
            project_id=active.project_id,
            site_id=active.site_id,
        )
        return Result.ok(active)

    async def _select(
        self, org: str, user: str, project_id: str, site_id: str | None
    ) -> ActiveContext:
        project = await self._projects.get_authorized_project(
            organization_id=org, user_id=user, project_id=project_id
        )
        if project is None:
            in_org = await self._projects.get_project_in_org(
                organization_id=org, project_id=project_id
            )
            if in_org is not None:
                raise errors.project_access_denied(org, user, project_id)
            raise errors.project_not_found(project_id)

        if site_id is not None:
            site = await self._sites.get_authorized_site(
                organization_id=org, user_id=user, site_id=site_id
            )
            if site is None:
                in_org = await self._sites.get_site_in_org(organization_id=org, site_id=site_id)
                if in_org is None:
                    raise errors.site_not_found(site_id)
                if in_org.project_id != project_id:
                    raise errors.project_site_mismatch(project_id, site_id)
                raise errors.site_access_denied(org, user, site_id)
            if site.project_id != project_id:
                raise errors.project_site_mismatch(project_id, site_id)

        return await self._active.set_active_context(
            organization_id=org,
            user_id=user,
            project_id=project_id,
            site_id=site_id,
            ttl_seconds=self._ttl,
        )

    async def clear_active_context(self, *, organization_id: str, user_id: str) -> Result[None]:
        try:
            await self._active.clear_active_context(
                organization_id=organization_id, user_id=user_id
            )
        except MesiriError as err:
            return Result.err(err)
        _log.info(
            "context.active_context_cleared",
            organization_id=organization_id,
            user_id=user_id,
        )
        return Result.ok(None)


def active_context_as_resolved(active: ActiveContext) -> ResolvedContext:
    """Convenience: render an active context as a (partial) ResolvedContext.

    Used by callers that want the active selection expressed in the shared
    contract shape (identity fields must be filled in by the caller).
    """
    return ResolvedContext(
        correlation_id=tracing.get_correlation_id() or "cor_unknown",
        source_message_id="",
        organization_id=active.organization_id,
        user_id=active.user_id,
        project_id=active.project_id,
        site_id=active.site_id,
        context_source=ContextSource.ACTIVE_CONTEXT,
        context_confidence=ContextConfidence.MEDIUM,
    )
