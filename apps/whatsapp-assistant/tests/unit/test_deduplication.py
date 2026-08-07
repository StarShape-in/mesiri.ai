"""Unit tests for WhatsApp message deduplication."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ingress.deduplication import InMemoryDeduplicationStore, RedisDeduplicationStore


@pytest.mark.asyncio
async def test_deduplication_ignores_duplicate_message_ids() -> None:
    store = InMemoryDeduplicationStore()

    assert await store.try_claim("wamid.123") is True
    assert await store.try_claim("wamid.123") is False
    assert await store.try_claim("wamid.456") is True


class _FakeRedis:
    """Minimal `_RedisLike` stand-in -- just the SET NX semantics dedup needs."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        self._store: dict[str, str] = {}
        self._raise_on_call = raise_on_call

    async def set_if_absent(
        self, key: str, value: str, *, ttl_seconds: int | None = None
    ) -> bool:
        if self._raise_on_call:
            raise ConnectionError("redis unavailable")
        if key in self._store:
            return False
        self._store[key] = value
        return True


@pytest.mark.asyncio
async def test_redis_deduplication_ignores_duplicate_message_ids() -> None:
    store = RedisDeduplicationStore(_FakeRedis(), ttl=timedelta(hours=1))

    assert await store.try_claim("wamid.123") is True
    assert await store.try_claim("wamid.123") is False
    assert await store.try_claim("wamid.456") is True


@pytest.mark.asyncio
async def test_redis_deduplication_fails_open_on_redis_error() -> None:
    """A Redis outage must not silently drop inbound messages -- see the
    class docstring in ingress/deduplication.py: dropping a real message is
    strictly worse than the rare double-process downstream idempotency keys
    already defend against."""
    store = RedisDeduplicationStore(_FakeRedis(raise_on_call=True))

    assert await store.try_claim("wamid.123") is True
