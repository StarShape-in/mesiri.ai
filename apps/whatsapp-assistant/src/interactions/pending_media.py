"""Redis-backed pending media BATCH (#2 Batch Media; short-lived, pop-once).

Engineers often send several photos in one burst (15 progress photos, a
stack of receipts). Every genuinely new image (not a tap answering the
purpose picker) is held here while the user picks what the WHOLE batch is
for -- then all of them are re-processed together once they tap. This used
to hold exactly ONE pending image per user: photo 15 silently overwrote
photos 1-14, and each arrival re-sent its own "what is this for?" picker.
Now a burst accumulates into one batch and the picker is asked exactly once
for it.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:pending_media
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from mesiri_contracts.assistant.normalized_message import NormalizedMessage

_DEFAULT_TTL_SECONDS = 600  # 10 minutes -- long enough to pick from a 2-row list

#: Hard cap on one batch. Bounds the Redis payload size and, more
#: importantly, the vision-analysis fan-out a single picker tap can trigger
#: -- a burst of 40 photos is far more likely to be an accidental multi-send
#: than a genuine 40-photo report.
MAX_BATCH_SIZE = 20


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class BatchAddResult:
    """What happened when one image was added to the batch.

    ``is_new_batch`` is the caller's signal for whether to send the purpose
    picker (True -- this is the first image of a fresh batch) or stay
    silent (False -- a picker is already pending for this batch; the photo
    was just appended to it). ``capped`` is True exactly when this image was
    the one that hit MAX_BATCH_SIZE -- the caller uses it to send one honest
    "that's as many as I can hold at once" note, not a note per rejected
    photo.
    """

    is_new_batch: bool
    batch_size: int
    capped: bool


class PendingMediaStore:
    """Stores a batch of pending NormalizedMessages (images) per user,
    consumed at most once as a whole."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:pending_media"

    async def add_pending(
        self,
        *,
        user_id: str,
        message: NormalizedMessage,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> BatchAddResult:
        """Append one image to the user's batch, starting a fresh one if
        none is pending. TTL is refreshed on every add -- a burst spread
        over several minutes must not have its earliest photos expire out
        from under it while later ones are still arriving."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        batch: list[dict[str, Any]] = list(raw) if isinstance(raw, list) else []
        is_new_batch = not batch

        if len(batch) >= MAX_BATCH_SIZE:
            # Already full -- this image is dropped, not silently discarded
            # without the caller knowing: capped=True on an unchanged batch
            # tells the caller to say so exactly once (not once per photo).
            return BatchAddResult(is_new_batch=False, batch_size=len(batch), capped=True)

        batch.append(message.model_dump(mode="json"))
        capped = len(batch) >= MAX_BATCH_SIZE
        await self._redis.set_json(key, batch, ttl_seconds=ttl_seconds)
        return BatchAddResult(is_new_batch=is_new_batch, batch_size=len(batch), capped=capped)

    async def pop_batch(self, *, user_id: str) -> list[NormalizedMessage]:
        """Read the whole pending batch and clear it in the same call -- a
        stale or expired batch must never resurrect later. Empty list (not
        None) when nothing is pending, since "no photos" and "batch
        expired" both mean the same thing to every caller: nothing to
        process."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw:
            return []
        await self._redis.set_json(key, [], ttl_seconds=1)
        return [NormalizedMessage.model_validate(item) for item in raw]

    async def has_pending(self, *, user_id: str) -> bool:
        """Non-destructive presence check -- for callers (memory/context_loader.py)
        that need to know *whether* a batch is held without consuming it."""
        raw = await self._redis.get_json(self._key(user_id))
        return bool(raw)
