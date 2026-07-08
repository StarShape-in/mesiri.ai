"""Context resolver production wiring and development diagnostics.

This module constructs the authoritative M4 ContextResolver using real
PostgreSQL adapters and FakeRedis for the active-context store (Redis wiring
is Phase 0 T5; see context/active_context.py for the real store).

The engine is built lazily from environment variables so tests that never
reach this path do not require a running database.
"""

from __future__ import annotations

import logging
import os

from context.active_context import RedisActiveContextStore
from context.postgres_repositories import (
    PostgresContextPreferenceRepository,
    PostgresExternalIdentityRepository,
    PostgresMembershipRepository,
    PostgresProjectRepository,
    PostgresRolePermissionRepository,
    PostgresSiteRepository,
)
from context.resolver import ContextDependencies, ContextResolver
from context.workflow_context import NullReplyContextProvider, NullWorkflowContextProvider
from mesiri_contracts.assistant.resolved_context import ResolvedContext

logger = logging.getLogger(__name__)


class _LazyAsyncEngine:
    """Defers SQLAlchemy engine creation to the first database query.

    Allows ``build_context_resolver()`` to run without sqlalchemy installed
    (sqlalchemy is an optional infra dependency absent in the fast unit-test
    lane). Only the ``connect()`` method is proxied because that is the only
    method used by the context repository mixins.
    """

    def __init__(self) -> None:
        self._engine = None

    def connect(self):  # returns the same async context manager as a real engine
        return self._get_engine().connect()

    def _get_engine(self):
        if self._engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine

            host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
            port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
            user_ = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
            password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
            database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
            dsn = f"postgresql+asyncpg://{user_}:{password}@{host}:{port}/{database}"
            self._engine = create_async_engine(dsn, echo=False, pool_pre_ping=True)
        return self._engine


def build_context_resolver() -> ContextResolver:
    """Construct the production M4 ContextResolver.

    Uses real PostgreSQL adapters for identity, membership, roles, projects,
    sites, and preferences. Uses FakeRedis for the active-context store until
    Phase 0 T5 wires the real RedisClient.

    The SQLAlchemy engine is built lazily on the first database query so that
    the resolver can be constructed in the fast unit-test lane (no sqlalchemy
    installed) without triggering import errors.
    """
    from mesiri.infrastructure.redis.client import FakeRedis

    engine = _LazyAsyncEngine()
    # T5: replace FakeRedis with a real RedisClient backed by MESIRI_REDIS__* settings.
    redis = FakeRedis()

    deps = ContextDependencies(
        identities=PostgresExternalIdentityRepository(engine),
        memberships=PostgresMembershipRepository(engine),
        roles=PostgresRolePermissionRepository(engine),
        projects=PostgresProjectRepository(engine),
        sites=PostgresSiteRepository(engine),
        preferences=PostgresContextPreferenceRepository(engine),
        active_context=RedisActiveContextStore(redis),
        reply_context=NullReplyContextProvider(),
        workflow_context=NullWorkflowContextProvider(),
    )
    return ContextResolver(deps)


def log_resolved_context(context: ResolvedContext) -> None:
    """Log the M4 ResolvedContext for development visibility (not user-facing)."""
    logger.info(
        "ResolvedContext correlation_id=%s user=%s org=%s project=%s site=%s "
        "source=%s confidence=%s",
        context.correlation_id,
        context.user_id or "unknown",
        context.organization_id or "unknown",
        context.project_id or "unknown",
        context.site_id or "unknown",
        context.context_source.value,
        context.context_confidence.value,
    )
    if context.role_ids:
        logger.info("ResolvedContext roles=%s", context.role_ids)
    if context.permissions:
        logger.info("ResolvedContext permissions=%s", context.permissions)
