"""Unit tests for runtime/inbound_journey/pending_decomposition.py."""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from runtime.inbound_journey.pending_decomposition import (
    PendingDecomposition,
    PendingDecompositionStore,
)

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


def _resolved(*, project_id: str | None = None, site_id: str | None = None) -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id=ORG,
        context_user_id=USR,
        context_project_id=project_id,
        context_site_id=site_id,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        permissions=["projects:write"],
    )


async def test_pop_pending_returns_none_when_nothing_held():
    store = PendingDecompositionStore(_FakeRedis())
    assert await store.pop_pending(user_id=USR) is None


async def test_set_then_pop_round_trips_segments_and_resolved_context():
    store = PendingDecompositionStore(_FakeRedis())
    pending = PendingDecomposition(
        segments=("create a project called Starship", "12 masons on site today"),
        resolved=_resolved(),
        expense_categories=("Materials", "Fuel"),
    )
    await store.set_pending(user_id=USR, pending=pending)

    popped = await store.pop_pending(user_id=USR)
    assert popped is not None
    assert popped.segments == pending.segments
    assert popped.resolved.organization_id == ORG
    assert popped.expense_categories == ("Materials", "Fuel")


async def test_pop_is_destructive():
    store = PendingDecompositionStore(_FakeRedis())
    await store.set_pending(
        user_id=USR,
        pending=PendingDecomposition(segments=("a",), resolved=_resolved(), expense_categories=None),
    )
    assert await store.pop_pending(user_id=USR) is not None
    assert await store.pop_pending(user_id=USR) is None


async def test_none_expense_categories_round_trips_as_none():
    store = PendingDecompositionStore(_FakeRedis())
    await store.set_pending(
        user_id=USR,
        pending=PendingDecomposition(segments=("a",), resolved=_resolved(), expense_categories=None),
    )
    popped = await store.pop_pending(user_id=USR)
    assert popped.expense_categories is None


async def test_pending_decompositions_are_scoped_per_user():
    store = PendingDecompositionStore(_FakeRedis())
    await store.set_pending(
        user_id=USR,
        pending=PendingDecomposition(segments=("a",), resolved=_resolved(), expense_categories=None),
    )
    assert await store.pop_pending(user_id="usr_other") is None
    assert await store.pop_pending(user_id=USR) is not None


async def test_clear_discards_without_returning():
    store = PendingDecompositionStore(_FakeRedis())
    await store.set_pending(
        user_id=USR,
        pending=PendingDecomposition(segments=("a",), resolved=_resolved(), expense_categories=None),
    )
    await store.clear(user_id=USR)
    assert await store.pop_pending(user_id=USR) is None


async def test_a_resolved_project_and_site_survive_the_round_trip():
    """The whole point: a second gate (site, after project) must see the
    project just picked, not a stale None."""
    store = PendingDecompositionStore(_FakeRedis())
    PRJ = "33333333-3333-4333-8333-333333333333"
    await store.set_pending(
        user_id=USR,
        pending=PendingDecomposition(
            segments=("a", "b"),
            resolved=_resolved(project_id=PRJ, site_id=None),
            expense_categories=None,
        ),
    )
    popped = await store.pop_pending(user_id=USR)
    assert popped.resolved.project_id == PRJ
    assert popped.resolved.site_id is None
