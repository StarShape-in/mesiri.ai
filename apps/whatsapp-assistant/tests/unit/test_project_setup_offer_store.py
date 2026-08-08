"""ProjectSetupOfferStore -- unit tests (fake Redis, no network)."""

from __future__ import annotations

from interactions.project_setup_offer import ProjectSetupOfferStore

USR = "22222222-2222-4222-8222-222222222222"
PROJ = "33333333-3333-4333-8333-333333333333"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key, value, *, ttl_seconds=None) -> None:
        self._store[key] = value

    async def get_json(self, key):
        return self._store.get(key)


async def test_set_then_pop_returns_the_offer_once():
    store = ProjectSetupOfferStore(_FakeRedis())
    await store.set_offer(user_id=USR, stage="site", project_id=PROJ)

    offer = await store.pop_offer(user_id=USR)

    assert offer is not None
    assert offer.stage == "site"
    assert offer.project_id == PROJ
    assert await store.pop_offer(user_id=USR) is None


async def test_pop_with_nothing_set_returns_none():
    store = ProjectSetupOfferStore(_FakeRedis())

    assert await store.pop_offer(user_id=USR) is None


async def test_clear_drops_the_offer_without_returning_it():
    store = ProjectSetupOfferStore(_FakeRedis())
    await store.set_offer(user_id=USR, stage="member", project_id=PROJ)

    await store.clear(user_id=USR)

    assert await store.pop_offer(user_id=USR) is None
