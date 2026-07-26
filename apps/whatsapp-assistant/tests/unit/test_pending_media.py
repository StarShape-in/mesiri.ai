"""Unit tests for PendingMediaStore — in-memory fake, no real Redis needed.

Mirrors test_pending_report.py's pattern exactly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from interactions.pending_media import PendingMediaStore
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    MediaReference,
    NormalizedMessage,
    SenderInfo,
)

USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, datetime | None]] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        expires = (
            datetime.now(UTC) + timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        )
        self._store[key] = (value, expires)

    async def get_json(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and expires <= datetime.now(UTC):
            return None
        return value


def _image_message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Ravi"),
        timestamp=datetime(2026, 7, 25, 10, 0, tzinfo=UTC),
        modality=InputModality.IMAGE,
        media=MediaReference(object_key="media/wamid.1/abc123", mime_type="image/jpeg", size_bytes=1024),
    )


async def test_pop_pending_returns_none_when_nothing_was_set():
    store = PendingMediaStore(_FakeRedis())
    assert await store.pop_pending(user_id=USR) is None


async def test_set_then_pop_returns_the_message_with_media_intact():
    store = PendingMediaStore(_FakeRedis())
    await store.set_pending(user_id=USR, message=_image_message())
    restored = await store.pop_pending(user_id=USR)
    assert restored is not None
    assert restored.modality is InputModality.IMAGE
    assert restored.media is not None
    assert restored.media.object_key == "media/wamid.1/abc123"


async def test_pop_is_consume_once():
    store = PendingMediaStore(_FakeRedis())
    await store.set_pending(user_id=USR, message=_image_message())
    await store.pop_pending(user_id=USR)
    assert await store.pop_pending(user_id=USR) is None


async def test_pending_media_is_scoped_per_user():
    store = PendingMediaStore(_FakeRedis())
    await store.set_pending(user_id=USR, message=_image_message())
    assert await store.pop_pending(user_id="usr_other") is None
    assert await store.pop_pending(user_id=USR) is not None
