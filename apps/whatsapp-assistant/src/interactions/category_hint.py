"""Redis-backed category-tap hint (short-lived, pop-once).

When a user taps a category on the greeting menu (see channel/replies.py
CATEGORY_ROWS), we remember which one for exactly their next message, then
forget it -- this is a nudge for extraction, never authoritative routing
(same "Redis is never authoritative" principle as context/active_context.py,
which this mirrors). A stale or missing hint must never break the journey;
callers get None and understanding falls back to its normal zero-context
classification.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:category_hint
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

_DEFAULT_TTL_SECONDS = 300  # 5 minutes -- long enough to reply, short enough not to linger


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class CategoryHint:
    """What a category tap remembered for the user's next message.

    ``direction`` is only ever set by the Material category's Arrived/Used
    buttons (see channel/replies.py MATERIAL_DIRECTION_BUTTONS) -- a fallback
    default for canonicalization to use only if the message's own words don't
    give a clear answer, never an override of what the user actually said.
    """

    semantic_hint: str | None
    direction: str | None = None


class CategoryHintStore:
    """Stores one pending category hint per user, consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:category_hint"

    async def set_hint(
        self,
        *,
        user_id: str,
        semantic_hint: str,
        direction: str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        await self._redis.set_json(
            self._key(user_id),
            {"semantic_hint": semantic_hint, "direction": direction},
            ttl_seconds=ttl_seconds,
        )

    async def pop_hint(self, *, user_id: str) -> CategoryHint | None:
        """Read the pending hint and clear it in the same call -- it applies to
        exactly one message, never lingers into an unrelated later one."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if raw is None or raw.get("semantic_hint") is None:
            # None either way: never set, or already consumed (the marker
            # written below leaves semantic_hint=None behind).
            return None
        # No delete primitive on the M1 client/fake -- overwrite with an
        # immediately-expired marker, same trick as active_context.clear_active_context.
        await self._redis.set_json(key, {"semantic_hint": None, "direction": None}, ttl_seconds=1)
        return CategoryHint(semantic_hint=raw.get("semantic_hint"), direction=raw.get("direction"))
