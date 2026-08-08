"""Unit tests for PendingReportStore — in-memory fake, no real Redis needed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2

ORG = "11111111-1111-4111-8111-111111111111"
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


def _event() -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 50, "unit": "bags"},
    )


async def test_pop_pending_returns_none_when_nothing_was_set():
    store = PendingReportStore(_FakeRedis())
    assert await store.pop_pending(user_id=USR) is None


async def test_set_then_pop_returns_the_event_with_fields_intact():
    store = PendingReportStore(_FakeRedis())
    await store.set_pending(user_id=USR, event=_event())
    restored = await store.pop_pending(user_id=USR)
    assert restored is not None
    assert restored.event_type is CanonicalEventType.MATERIAL_RECEIPT_REQUESTED
    assert restored.fields == {"material_name": "cement", "quantity": 50, "unit": "bags"}


async def test_pop_is_consume_once():
    store = PendingReportStore(_FakeRedis())
    await store.set_pending(user_id=USR, event=_event())
    await store.pop_pending(user_id=USR)
    assert await store.pop_pending(user_id=USR) is None


async def test_pending_reports_are_scoped_per_user():
    store = PendingReportStore(_FakeRedis())
    await store.set_pending(user_id=USR, event=_event())
    assert await store.pop_pending(user_id="usr_other") is None
    assert await store.pop_pending(user_id=USR) is not None
