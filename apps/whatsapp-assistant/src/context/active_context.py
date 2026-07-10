"""Redis-backed active context store (M4).

Stores the user's *ephemeral* active project/site behind the Redis boundary. Key
layout (the client prepends the ``mesiri`` namespace):

    mesiri:{organization_id}:user:{user_id}:active_context

The value carries ``selected_at`` / ``expires_at`` / ``context_version`` so the
selection survives an application restart (Redis persists it) and expiry is
enforced explicitly — belt-and-braces with Redis TTL, and correct even against
the in-memory ``FakeRedis`` which does not emulate TTL eviction.

Redis is NEVER authoritative: the resolver revalidates the stored project/site
against PostgreSQL authorization before using it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .models import ActiveContext

CONTEXT_VERSION = 1


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


def _now() -> datetime:
    return datetime.now(UTC)


class RedisActiveContextStore:
    """Active context store over the M1 ``RedisClient`` / ``FakeRedis`` interface."""

    def __init__(self, redis: _RedisLike, *, clock: Callable[[], datetime] = _now) -> None:
        self._redis = redis
        self._clock = clock

    @staticmethod
    def _key(organization_id: str, user_id: str) -> str:
        return f"{organization_id}:user:{user_id}:active_context"

    async def get_active_context(
        self, *, organization_id: str, user_id: str
    ) -> ActiveContext | None:
        raw = await self._redis.get_json(self._key(organization_id, user_id))
        if raw is None:
            return None
        expires_at = raw.get("expires_at")
        if expires_at is not None and datetime.fromisoformat(expires_at) <= self._clock():
            return None  # expired (TTL belt-and-braces)
        return ActiveContext(
            organization_id=organization_id,
            user_id=user_id,
            project_id=raw.get("project_id"),
            site_id=raw.get("site_id"),
            selected_at=raw.get("selected_at", ""),
            expires_at=expires_at or "",
            context_version=int(raw.get("context_version", CONTEXT_VERSION)),
        )

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
        expires_at = now + timedelta(seconds=ttl_seconds)
        payload = {
            "project_id": project_id,
            "site_id": site_id,
            "selected_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "context_version": CONTEXT_VERSION,
        }
        await self._redis.set_json(
            self._key(organization_id, user_id), payload, ttl_seconds=ttl_seconds
        )
        return ActiveContext(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            site_id=site_id,
            selected_at=payload["selected_at"],
            expires_at=payload["expires_at"],
            context_version=CONTEXT_VERSION,
        )

    async def clear_active_context(self, *, organization_id: str, user_id: str) -> None:
        # Overwrite with an immediately-expired marker; works on set_json-only
        # interfaces (no delete primitive exposed by the M1 client / fake).
        await self._redis.set_json(
            self._key(organization_id, user_id),
            {
                "project_id": None,
                "site_id": None,
                "selected_at": self._clock().isoformat(),
                "expires_at": self._clock().isoformat(),
                "context_version": CONTEXT_VERSION,
            },
            ttl_seconds=1,
        )
