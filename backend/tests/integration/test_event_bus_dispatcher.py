"""Integration tests for mesiri.events.bus.dispatcher (#14 Event Bus).

Live Postgres required (see test_timeline_projector.py -- same fixture
shape). Covers what a fakes-only unit test cannot: real savepoint rollback
on a failing consumer, the anti-join against event_consumer_checkpoints,
and two independent consumers reading the SAME outbox rows without
interfering with each other.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.events.bus import drain_for_consumer

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM event_consumer_checkpoints"))
        await conn.execute(sa.text("DELETE FROM outbox_events"))
    yield


async def _insert_outbox_event(engine: AsyncEngine, *, event_type: str = "TestEvent") -> uuid.UUID:
    row_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO outbox_events "
                "(id, aggregate_type, aggregate_id, event_type, payload, correlation_id, created_at) "
                "VALUES (:id, 'test_aggregate', :id, :event_type, '{}'::jsonb, 'cor_1', now())"
            ),
            {"id": row_id, "event_type": event_type},
        )
    return row_id


class _RecordingConsumer:
    """Records every event it's handed; never fails."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: list[uuid.UUID] = []

    async def handle(self, conn, event: dict) -> None:
        self.seen.append(event["id"])


class _AlwaysFailingConsumer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attempts = 0

    async def handle(self, conn, event: dict) -> None:
        self.attempts += 1
        raise RuntimeError("simulated consumer failure")


class _FailsOnceConsumer:
    """Fails the first time it sees a given event, succeeds after that --
    exercises the "unchecked row is retried on the next drain" model."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._failed_once: set[uuid.UUID] = set()
        self.succeeded: list[uuid.UUID] = []

    async def handle(self, conn, event: dict) -> None:
        if event["id"] not in self._failed_once:
            self._failed_once.add(event["id"])
            raise RuntimeError("first attempt always fails")
        self.succeeded.append(event["id"])


async def test_a_consumer_processes_unseen_rows_and_they_are_checkpointed(
    test_engine: AsyncEngine, clean_db
):
    event_id = await _insert_outbox_event(test_engine)
    consumer = _RecordingConsumer("recorder_a")

    async with test_engine.begin() as conn:
        result = await drain_for_consumer(conn, consumer, batch_size=100)

    assert result.processed == 1
    assert result.failed == 0
    assert consumer.seen == [event_id]

    async with test_engine.begin() as conn:
        checkpoint = (
            await conn.execute(
                sa.text(
                    "SELECT 1 FROM event_consumer_checkpoints "
                    "WHERE consumer_name = :name AND event_id = :event_id"
                ),
                {"name": "recorder_a", "event_id": event_id},
            )
        ).first()
    assert checkpoint is not None


async def test_a_second_drain_does_not_reprocess_a_checkpointed_row(
    test_engine: AsyncEngine, clean_db
):
    await _insert_outbox_event(test_engine)
    consumer = _RecordingConsumer("recorder_b")

    async with test_engine.begin() as conn:
        await drain_for_consumer(conn, consumer, batch_size=100)
    async with test_engine.begin() as conn:
        second = await drain_for_consumer(conn, consumer, batch_size=100)

    assert second.processed == 0
    assert second.batch_size == 0
    assert len(consumer.seen) == 1  # not handed the row twice


async def test_two_independent_consumers_both_see_the_same_row(
    test_engine: AsyncEngine, clean_db
):
    """The whole point of event_consumer_checkpoints over outbox_events.
    published_at: consumer A completing must not hide the row from
    consumer B."""
    event_id = await _insert_outbox_event(test_engine)
    consumer_a = _RecordingConsumer("consumer_a")
    consumer_b = _RecordingConsumer("consumer_b")

    async with test_engine.begin() as conn:
        await drain_for_consumer(conn, consumer_a, batch_size=100)
    async with test_engine.begin() as conn:
        await drain_for_consumer(conn, consumer_b, batch_size=100)

    assert consumer_a.seen == [event_id]
    assert consumer_b.seen == [event_id]


async def test_a_failing_consumer_does_not_get_checkpointed(test_engine: AsyncEngine, clean_db):
    event_id = await _insert_outbox_event(test_engine)
    consumer = _AlwaysFailingConsumer("always_fails")

    async with test_engine.begin() as conn:
        result = await drain_for_consumer(conn, consumer, batch_size=100)

    assert result.processed == 0
    assert result.failed == 1
    assert consumer.attempts == 1

    async with test_engine.begin() as conn:
        checkpoint = (
            await conn.execute(
                sa.text(
                    "SELECT 1 FROM event_consumer_checkpoints "
                    "WHERE consumer_name = :name AND event_id = :event_id"
                ),
                {"name": "always_fails", "event_id": event_id},
            )
        ).first()
    assert checkpoint is None


async def test_a_failure_is_retried_on_the_next_drain_and_can_then_succeed(
    test_engine: AsyncEngine, clean_db
):
    event_id = await _insert_outbox_event(test_engine)
    consumer = _FailsOnceConsumer("fails_once")

    async with test_engine.begin() as conn:
        first = await drain_for_consumer(conn, consumer, batch_size=100)
    assert first.processed == 0
    assert first.failed == 1

    async with test_engine.begin() as conn:
        second = await drain_for_consumer(conn, consumer, batch_size=100)
    assert second.processed == 1
    assert second.failed == 0
    assert consumer.succeeded == [event_id]


async def test_one_bad_row_does_not_block_the_rest_of_the_batch(
    test_engine: AsyncEngine, clean_db
):
    """The savepoint-per-row design's whole reason to exist: without it, one
    raised exception mid-batch would poison the transaction for every
    subsequent checkpoint INSERT (Postgres refuses further statements in an
    aborted transaction)."""
    good_1 = await _insert_outbox_event(test_engine)
    bad = await _insert_outbox_event(test_engine)
    good_2 = await _insert_outbox_event(test_engine)

    class _FailsOnOneEvent:
        name = "selective_failure"

        def __init__(self) -> None:
            self.seen: list[uuid.UUID] = []

        async def handle(self, conn, event: dict) -> None:
            self.seen.append(event["id"])
            if event["id"] == bad:
                raise RuntimeError("this one is bad")

    consumer = _FailsOnOneEvent()
    async with test_engine.begin() as conn:
        result = await drain_for_consumer(conn, consumer, batch_size=100)

    assert result.processed == 2
    assert result.failed == 1
    assert set(consumer.seen) == {good_1, bad, good_2}

    async with test_engine.begin() as conn:
        checkpointed = {
            row["event_id"]
            for row in (
                await conn.execute(
                    sa.text(
                        "SELECT event_id FROM event_consumer_checkpoints WHERE consumer_name = :name"
                    ),
                    {"name": "selective_failure"},
                )
            )
            .mappings()
            .all()
        }
    assert checkpointed == {good_1, good_2}


async def test_batch_size_smaller_than_requested_signals_caught_up(
    test_engine: AsyncEngine, clean_db
):
    await _insert_outbox_event(test_engine)
    await _insert_outbox_event(test_engine)
    consumer = _RecordingConsumer("small_batch")

    async with test_engine.begin() as conn:
        result = await drain_for_consumer(conn, consumer, batch_size=100)

    # 2 rows requested with room for 100 -> batch_size reflects what was
    # actually available, the signal scripts/run_event_consumers.py's loop
    # uses to know it has caught up.
    assert result.batch_size == 2
