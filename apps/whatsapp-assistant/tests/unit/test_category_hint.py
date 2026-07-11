"""Unit tests for CategoryHintStore — in-memory fake, no real Redis needed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from interactions.category_hint import CategoryHintStore


class _FakeRedis:
    """Minimal stand-in for the M1 Redis client's json+ttl interface."""

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


async def test_pop_hint_returns_none_when_nothing_was_set():
    store = CategoryHintStore(_FakeRedis())
    assert await store.pop_hint(user_id="usr_1") is None


async def test_set_then_pop_returns_the_hint():
    store = CategoryHintStore(_FakeRedis())
    await store.set_hint(user_id="usr_1", semantic_hint="material_update")
    assert await store.pop_hint(user_id="usr_1") == "material_update"


async def test_pop_is_consume_once():
    store = CategoryHintStore(_FakeRedis())
    await store.set_hint(user_id="usr_1", semantic_hint="expense")
    await store.pop_hint(user_id="usr_1")
    assert await store.pop_hint(user_id="usr_1") is None


async def test_hints_are_scoped_per_user():
    store = CategoryHintStore(_FakeRedis())
    await store.set_hint(user_id="usr_1", semantic_hint="material_update")
    assert await store.pop_hint(user_id="usr_2") is None
    assert await store.pop_hint(user_id="usr_1") == "material_update"


async def test_changing_the_selection_immediately_overrides_the_pending_hint():
    """Tapping a different category before the first hint is consumed must
    switch it right away -- never wait out the old TTL, never queue both."""
    store = CategoryHintStore(_FakeRedis())
    await store.set_hint(user_id="usr_1", semantic_hint="material_update")
    await store.set_hint(user_id="usr_1", semantic_hint="equipment_usage")
    assert await store.pop_hint(user_id="usr_1") == "equipment_usage"


async def test_switching_categories_repeatedly_always_reflects_the_latest_tap():
    store = CategoryHintStore(_FakeRedis())
    for hint in ("material_update", "labour_update", "expense", "equipment_usage"):
        await store.set_hint(user_id="usr_1", semantic_hint=hint)
    assert await store.pop_hint(user_id="usr_1") == "equipment_usage"
