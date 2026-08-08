"""Serve just-written objects from memory instead of re-fetching them (perf).

An ``ObjectStoragePort`` decorator, not a new backing store: every call still
reaches the wrapped adapter, this only answers ``get_object`` from memory when
the same key was written moments ago by this process.

The case it exists for: WhatsApp media makes three network hops for one photo.
``ingress/receiver.py`` downloads the bytes from Meta's CDN (they are in
memory), uploads them to R2, and then ``understanding/pipeline.py``'s
``_read_media`` immediately fetches the *same bytes back out of R2* to hand to
the vision/speech provider. The second read is pure waste -- the bytes never
left the process.

Bounded and self-evicting, because a cache that grows on failure is worse than
the round trip it saves:

- an entry is dropped as soon as it's read (the read-back happens once, right
  after the write -- there is no second consumer)
- entries are dropped oldest-first past ``max_entries`` / ``max_total_bytes``,
  so a message that dies between ingress and understanding leaks nothing
- a payload larger than ``max_object_bytes`` is never retained at all
- a miss is completely ordinary: ``get_object`` just calls through, which is
  also what makes the admin replay/retry path (which re-reads media long
  after the write) keep working unchanged
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from mesiri_contracts.common.storage import ObjectMetadata, ObjectStoragePort, StoredObject

logger = logging.getLogger(__name__)

# A WhatsApp photo is 1-3MB and a voice note far less, so these bound the
# cache at a few tens of MB in the worst case while comfortably covering
# normal concurrency.
_MAX_ENTRIES = 32
_MAX_OBJECT_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024


class RecentWritesCachingObjectStorage:
    """Wraps an ObjectStoragePort, serving recently-written keys from memory."""

    def __init__(
        self,
        inner: ObjectStoragePort,
        *,
        max_entries: int = _MAX_ENTRIES,
        max_object_bytes: int = _MAX_OBJECT_BYTES,
        max_total_bytes: int = _MAX_TOTAL_BYTES,
    ) -> None:
        self._inner = inner
        self._max_entries = max_entries
        self._max_object_bytes = max_object_bytes
        self._max_total_bytes = max_total_bytes
        self._entries: OrderedDict[str, tuple[bytes, str | None]] = OrderedDict()
        self._total_bytes = 0
        # Health/readiness checks introspect the wrapped adapter by attribute
        # (see infrastructure health registration), so mirror its identity
        # rather than presenting this decorator as a distinct dependency.
        self.name = getattr(inner, "name", "object_storage")
        self.required = getattr(inner, "required", True)

    def _evict(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._total_bytes -= len(entry[0])

    def _retain(self, key: str, data: bytes, content_type: str | None) -> None:
        if len(data) > self._max_object_bytes:
            return
        self._evict(key)
        self._entries[key] = (data, content_type)
        self._total_bytes += len(data)
        while self._entries and (
            len(self._entries) > self._max_entries or self._total_bytes > self._max_total_bytes
        ):
            oldest, _ = next(iter(self._entries.items()))
            self._evict(oldest)

    async def put_object(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> ObjectMetadata:
        metadata = await self._inner.put_object(key, data, content_type=content_type)
        # Retained only after the real write succeeds -- never serve a read
        # for bytes that aren't actually durable.
        self._retain(key, bytes(data), content_type)
        return metadata

    async def get_object(self, key: str) -> StoredObject:
        entry = self._entries.get(key)
        if entry is None:
            return await self._inner.get_object(key)
        # Single-consumer by design: drop it now rather than waiting for size
        # pressure, so the common path holds nothing after the handoff.
        self._evict(key)
        data, content_type = entry
        logger.debug("object_storage.served_from_recent_writes key=%s bytes=%s", key, len(data))
        return StoredObject(key=key, data=data, content_type=content_type)

    async def head_object(self, key: str) -> ObjectMetadata:
        return await self._inner.head_object(key)

    async def delete_object(self, key: str) -> None:
        self._evict(key)
        await self._inner.delete_object(key)

    async def generate_presigned_url(
        self, key: str, *, expires_in_seconds: int = 900, method: str = "GET"
    ) -> str:
        return await self._inner.generate_presigned_url(
            key, expires_in_seconds=expires_in_seconds, method=method
        )

    async def health_check(self) -> None:
        await self._inner.health_check()
