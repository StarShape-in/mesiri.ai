"""Redis-backed pending report (short-lived, pop-once).

When a report is otherwise complete (material_name/quantity/unit all
present) but no project could be resolved for the sender (multi-project
access, no active/default project set -- see context/resolver.py's
single-project convenience), we hold the extracted CanonicalEvent here
while the user picks a project from a list, then resume with it filled in.
Mirrors interactions/category_hint.py's store/pop-once pattern exactly.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:pending_report
"""

from __future__ import annotations

from typing import Any, Protocol

from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2

_DEFAULT_TTL_SECONDS = 600  # 10 minutes -- long enough to pick a project from a list


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class PendingReportStore:
    """Stores one pending CanonicalEventV2 per user, consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:pending_report"

    async def set_pending(
        self, *, user_id: str, event: CanonicalEventV2, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._redis.set_json(
            self._key(user_id), event.model_dump(mode="json"), ttl_seconds=ttl_seconds
        )

    async def pop_pending(self, *, user_id: str) -> CanonicalEventV2 | None:
        """Read the pending report and clear it in the same call -- a stale or
        expired selection must never resurrect an old report."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw:
            return None
        await self._redis.set_json(key, {}, ttl_seconds=1)
        return CanonicalEventV2.model_validate(raw)

    async def has_pending(self, *, user_id: str) -> bool:
        """Non-destructive presence check -- for callers (memory/context_loader.py)
        that need to know *whether* a report is held without consuming it."""
        raw = await self._redis.get_json(self._key(user_id))
        return bool(raw)
