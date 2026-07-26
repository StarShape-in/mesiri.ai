"""Redis-backed pending media (short-lived, pop-once).

Every genuinely new image (not a tap answering this very picker) is held
here while the user picks what it's for (see channel/replies.py's
IMAGE_PURPOSE_ROWS) -- then re-processed with that answer as a semantic_hint
once they tap. Mirrors interactions/pending_report.py's store/pop-once
pattern exactly, but holds the *pre-understanding* NormalizedMessage itself
(pending_report only ever exists after understanding has already produced a
CanonicalEvent) -- this is the one pending-state store that exists purely
so understanding can be deferred until the user answers "what is this for?".

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:pending_media
"""

from __future__ import annotations

from typing import Any, Protocol

from mesiri_contracts.assistant.normalized_message import NormalizedMessage

_DEFAULT_TTL_SECONDS = 600  # 10 minutes -- long enough to pick from a 2-row list


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class PendingMediaStore:
    """Stores one pending NormalizedMessage (an image) per user, consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:pending_media"

    async def set_pending(
        self, *, user_id: str, message: NormalizedMessage, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._redis.set_json(
            self._key(user_id), message.model_dump(mode="json"), ttl_seconds=ttl_seconds
        )

    async def pop_pending(self, *, user_id: str) -> NormalizedMessage | None:
        """Read the pending image and clear it in the same call -- a stale or
        expired selection must never resurrect an old photo."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw:
            return None
        await self._redis.set_json(key, {}, ttl_seconds=1)
        return NormalizedMessage.model_validate(raw)
