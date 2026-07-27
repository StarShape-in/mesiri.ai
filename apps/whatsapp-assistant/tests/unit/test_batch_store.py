"""Unit tests for PendingBatchStore (#1 Multi-Activity) — in-memory fake, no
real Redis needed. Mirrors test_pending_report.py's pattern.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from workflows.batch_store import PendingBatchStore

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


def _event(event_type: CanonicalEventType = CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED, **fields):
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=event_type,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )


async def test_has_pending_false_when_never_started():
    store = PendingBatchStore(_FakeRedis())
    assert await store.has_pending(user_id=USR) is False


async def test_pop_next_returns_none_when_nothing_queued():
    store = PendingBatchStore(_FakeRedis())
    assert await store.pop_next(user_id=USR) is None


async def test_start_batch_then_pop_next_returns_first_queued_segment_with_correct_progress():
    store = PendingBatchStore(_FakeRedis())
    seg2 = _event(narrative="started painting")
    seg3 = _event(narrative="repaired columns")
    await store.start_batch(user_id=USR, remaining=[seg2, seg3], total=3)

    result = await store.pop_next(user_id=USR)
    assert result is not None
    event, progress = result
    assert event.fields["narrative"] == "started painting"
    assert progress.index == 2  # segment 1 already ran outside the queue
    assert progress.total == 3
    assert progress.outcomes == ()


async def test_pop_next_advances_through_the_whole_queue_then_returns_none():
    store = PendingBatchStore(_FakeRedis())
    seg2 = _event(narrative="b")
    seg3 = _event(narrative="c")
    await store.start_batch(user_id=USR, remaining=[seg2, seg3], total=3)

    first = await store.pop_next(user_id=USR)
    assert first is not None
    assert first[1].index == 2

    second = await store.pop_next(user_id=USR)
    assert second is not None
    assert second[0].fields["narrative"] == "c"
    assert second[1].index == 3

    assert await store.pop_next(user_id=USR) is None


async def test_record_outcome_numbers_lines_in_order():
    store = PendingBatchStore(_FakeRedis())
    await store.start_batch(user_id=USR, remaining=[_event()], total=2)

    await store.record_outcome(user_id=USR, outcome="Recorded.")
    await store.record_outcome(user_id=USR, outcome="Discarded.")

    outcomes = await store.get_outcomes(user_id=USR)
    assert outcomes == ("1. Recorded.", "2. Discarded.")


async def test_record_outcome_on_a_never_started_batch_is_a_safe_no_op():
    store = PendingBatchStore(_FakeRedis())
    await store.record_outcome(user_id=USR, outcome="Recorded.")
    assert await store.get_outcomes(user_id=USR) == ()


async def test_clear_empties_the_batch():
    store = PendingBatchStore(_FakeRedis())
    await store.start_batch(user_id=USR, remaining=[_event()], total=2)
    assert await store.has_pending(user_id=USR) is True

    await store.clear(user_id=USR)
    assert await store.has_pending(user_id=USR) is False
    assert await store.pop_next(user_id=USR) is None


async def test_batches_are_scoped_per_user():
    store = PendingBatchStore(_FakeRedis())
    await store.start_batch(user_id=USR, remaining=[_event()], total=2)
    assert await store.has_pending(user_id="usr_other") is False
    assert await store.has_pending(user_id=USR) is True
