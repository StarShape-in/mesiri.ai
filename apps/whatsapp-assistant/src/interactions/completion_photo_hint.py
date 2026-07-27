"""Redis-backed "waiting for a completion photo" hint (#25 AI Follow-up).

When an Activity is marked COMPLETED, Mesiri proactively asks "want to
attach a completion photo?" (see interactions/handler.py's
_resume_and_render). This hint remembers WHICH activity that offer was
about, so the very next photo the same user sends attaches directly to it
-- skipping the normal "what is this photo for?" picker (see
runtime/dependencies.py's image-arrival block) -- instead of making the
user answer a picker for a question Mesiri just asked and they're plainly
answering by sending the photo.

Mirrors interactions/category_hint.py's store/pop-once pattern exactly (same
"Redis is a hint, never authoritative" principle): a stale or missing hint
must never break the journey, and popping never resurrects itself for a
later, unrelated photo.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:completion_photo_hint
"""

from __future__ import annotations

from typing import Any, Protocol

_DEFAULT_TTL_SECONDS = 900  # 15 minutes -- long enough to walk over and take the photo


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class CompletionPhotoHintStore:
    """Stores one pending "which activity is the next photo for" hint per
    user, consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:completion_photo_hint"

    async def set_hint(
        self, *, user_id: str, activity_id: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._redis.set_json(
            self._key(user_id), {"activity_id": activity_id}, ttl_seconds=ttl_seconds
        )

    async def pop_hint(self, *, user_id: str) -> str | None:
        """Read the pending activity_id and clear it in the same call -- it
        applies to exactly the next photo, never lingers into a later,
        unrelated one."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw or not raw.get("activity_id"):
            return None
        await self._redis.set_json(key, {"activity_id": None}, ttl_seconds=1)
        return str(raw["activity_id"])
