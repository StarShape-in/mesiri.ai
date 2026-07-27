"""Redis-backed current-activity / current-date scopes (pop-never, TTL'd).

Unlike interactions/pending_report.py's pop-once shape, these are read-many:
"current activity" must still answer on the *third* follow-up message in a
row, not only the first. They are overwritten (not appended) on every write,
same as context/active_context.py's single active project/site slot.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:current_activity
    mesiri:user:{user_id}:current_date
"""

from __future__ import annotations

from typing import Any, Protocol

from .requirements import CURRENT_ACTIVITY, CURRENT_DATE


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class CurrentActivityStore:
    """The Activity most recently created/continued in this conversation.

    A HINT only (see memory/requirements.py) -- the caller must confirm the
    activity is still open in Postgres before treating it as the target of a
    continuation, the same way runtime.activity_query's own lookup already
    filters to PLANNED/IN_PROGRESS. This store exists to prefer *this
    conversation's* own activity over that lookup's site-wide "most recently
    updated" guess when both are available.
    """

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:current_activity"

    async def set_current(
        self, *, user_id: str, activity_id: str, ttl_seconds: int = CURRENT_ACTIVITY.ttl_seconds
    ) -> None:
        await self._redis.set_json(self._key(user_id), {"activity_id": activity_id}, ttl_seconds=ttl_seconds)

    async def get_current(self, *, user_id: str) -> str | None:
        raw = await self._redis.get_json(self._key(user_id))
        if not raw:
            return None
        activity_id = raw.get("activity_id")
        return str(activity_id) if activity_id else None

    async def clear(self, *, user_id: str) -> None:
        # No delete primitive on the M1 client/fake -- overwrite with an
        # immediately-expired marker, same trick as active_context.py's
        # clear_active_context.
        await self._redis.set_json(self._key(user_id), {"activity_id": None}, ttl_seconds=1)


class CurrentDateStore:
    """A date the user explicitly stated in this conversation ('for yesterday').

    Only ever set from an *explicit* statement, never inferred -- the caller
    is responsible for that distinction (mirrors canonicalization/
    occurred_date.py's own source-tagging: an inferred date must never be
    silently promoted to something later code treats as user-stated).
    """

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:current_date"

    async def set_current(
        self, *, user_id: str, occurred_date: str, ttl_seconds: int = CURRENT_DATE.ttl_seconds
    ) -> None:
        await self._redis.set_json(
            self._key(user_id), {"occurred_date": occurred_date}, ttl_seconds=ttl_seconds
        )

    async def get_current(self, *, user_id: str) -> str | None:
        raw = await self._redis.get_json(self._key(user_id))
        if not raw:
            return None
        value = raw.get("occurred_date")
        return str(value) if value else None
