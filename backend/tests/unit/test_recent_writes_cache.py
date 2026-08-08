"""RecentWritesCachingObjectStorage serves just-written bytes from memory.

The behaviour under test exists to remove one of three network hops a single
WhatsApp photo used to make: Meta CDN -> R2 -> back out of R2 again for the
vision call. See recent_writes_cache.py's module docstring.
"""

from __future__ import annotations

import pytest

from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri.infrastructure.objectstorage.recent_writes_cache import (
    RecentWritesCachingObjectStorage,
)


class CountingObjectStorage(FakeObjectStorage):
    """FakeObjectStorage that records how often it is actually reached."""

    def __init__(self) -> None:
        super().__init__()
        self.get_calls = 0
        self.put_calls = 0

    async def put_object(self, key, data, *, content_type=None):
        self.put_calls += 1
        return await super().put_object(key, data, content_type=content_type)

    async def get_object(self, key):
        self.get_calls += 1
        return await super().get_object(key)


@pytest.mark.anyio
async def test_read_after_write_does_not_touch_the_backing_store():
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner)

    await storage.put_object("media/m1", b"jpeg-bytes", content_type="image/jpeg")
    obj = await storage.get_object("media/m1")

    assert obj.data == b"jpeg-bytes"
    assert obj.content_type == "image/jpeg"
    # The write still went through; the read never did.
    assert inner.put_calls == 1
    assert inner.get_calls == 0


@pytest.mark.anyio
async def test_entry_is_dropped_after_one_read_so_a_second_read_falls_through():
    """Single-consumer by design -- the read-back happens once, right after
    the write. Holding the bytes past that point would just be a leak."""
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner)

    await storage.put_object("media/m1", b"jpeg-bytes")
    await storage.get_object("media/m1")
    obj = await storage.get_object("media/m1")

    assert obj.data == b"jpeg-bytes"  # still correct, just fetched for real
    assert inner.get_calls == 1


@pytest.mark.anyio
async def test_a_key_never_written_here_reads_straight_through():
    """A miss is completely ordinary -- this is what keeps the admin
    replay/retry path (which re-reads media long after the write) working."""
    inner = CountingObjectStorage()
    await inner.put_object("media/old", b"written-before-the-wrapper-existed")
    storage = RecentWritesCachingObjectStorage(inner)

    obj = await storage.get_object("media/old")

    assert obj.data == b"written-before-the-wrapper-existed"
    assert inner.get_calls == 1


@pytest.mark.anyio
async def test_oversized_payloads_are_never_retained():
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner, max_object_bytes=8)

    await storage.put_object("media/big", b"much longer than eight bytes")
    await storage.get_object("media/big")

    assert inner.get_calls == 1


@pytest.mark.anyio
async def test_unread_entries_are_evicted_oldest_first_under_pressure():
    """A message that dies between ingress and understanding never gets its
    read -- max_entries is what stops those from accumulating."""
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner, max_entries=2)

    await storage.put_object("media/1", b"one")
    await storage.put_object("media/2", b"two")
    await storage.put_object("media/3", b"three")

    # media/1 was pushed out; the two most recent are still served from memory.
    await storage.get_object("media/1")
    assert inner.get_calls == 1
    await storage.get_object("media/2")
    await storage.get_object("media/3")
    assert inner.get_calls == 1


@pytest.mark.anyio
async def test_a_failed_write_is_not_served_from_memory():
    """Never answer a read with bytes that aren't actually durable."""

    class FailingStorage(CountingObjectStorage):
        async def put_object(self, key, data, *, content_type=None):
            raise RuntimeError("bucket unreachable")

    inner = FailingStorage()
    storage = RecentWritesCachingObjectStorage(inner)

    with pytest.raises(RuntimeError):
        await storage.put_object("media/m1", b"jpeg-bytes")

    from mesiri_contracts.common.errors import MesiriError

    with pytest.raises(MesiriError):
        await storage.get_object("media/m1")


@pytest.mark.anyio
async def test_delete_drops_the_cached_copy_too():
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner)

    await storage.put_object("media/m1", b"jpeg-bytes")
    await storage.delete_object("media/m1")

    from mesiri_contracts.common.errors import MesiriError

    with pytest.raises(MesiriError):
        await storage.get_object("media/m1")


@pytest.mark.anyio
async def test_it_presents_the_wrapped_adapters_health_identity():
    """Readiness checks introspect the adapter by attribute, so the decorator
    must not surface itself as a separate dependency."""
    inner = CountingObjectStorage()
    storage = RecentWritesCachingObjectStorage(inner)

    assert storage.name == inner.name
    assert storage.required == inner.required
    await storage.health_check()
