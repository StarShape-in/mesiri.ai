"""Unit tests for CompletionPhotoHintStore (#25 AI Follow-up) — in-memory
fake, no real Redis needed. Mirrors test_category_hint.py's pattern."""

from __future__ import annotations

from typing import Any

from interactions.completion_photo_hint import CompletionPhotoHintStore

USR = "22222222-2222-4222-8222-222222222222"
ACTIVITY = "33333333-3333-4333-8333-333333333333"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


async def test_pop_hint_returns_none_when_nothing_was_set():
    store = CompletionPhotoHintStore(_FakeRedis())
    assert await store.pop_hint(user_id=USR) is None


async def test_set_then_pop_returns_the_activity_id():
    store = CompletionPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, activity_id=ACTIVITY)
    assert await store.pop_hint(user_id=USR) == ACTIVITY


async def test_pop_is_consume_once():
    store = CompletionPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, activity_id=ACTIVITY)
    await store.pop_hint(user_id=USR)
    assert await store.pop_hint(user_id=USR) is None


async def test_hints_are_scoped_per_user():
    store = CompletionPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, activity_id=ACTIVITY)
    assert await store.pop_hint(user_id="usr_other") is None
    assert await store.pop_hint(user_id=USR) == ACTIVITY


async def test_setting_a_new_hint_replaces_the_old_one():
    store = CompletionPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, activity_id="old-activity")
    await store.set_hint(user_id=USR, activity_id=ACTIVITY)
    assert await store.pop_hint(user_id=USR) == ACTIVITY
