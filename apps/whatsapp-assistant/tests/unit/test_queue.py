"""Unit tests for the durable ARQ ingress queue (runtime/queue.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ingress.receiver import MessageIngressContext
from runtime.queue import (
    HEALTH_CHECK_KEY,
    PROCESS_MESSAGE_JOB,
    QUEUE_NAME,
    MessageEnqueuer,
    context_from_envelope,
    parse_worker_health,
)


def _context() -> MessageIngressContext:
    return MessageIngressContext(
        message={"id": "wamid.123", "from": "15551234567", "type": "text"},
        contacts=({"profile": {"name": "Alan"}},),
        phone_number_id="pn-1",
        display_phone_number="+1 555 123 4567",
    )


@pytest.mark.asyncio
async def test_enqueuer_writes_a_replayable_envelope_as_an_arq_job() -> None:
    enqueuer = MessageEnqueuer.__new__(MessageEnqueuer)  # bypass connect(); inject pool directly
    pool = AsyncMock()
    enqueuer._pool = pool

    await enqueuer(_context())

    pool.enqueue_job.assert_awaited_once()
    args, kwargs = pool.enqueue_job.call_args
    assert args[0] == PROCESS_MESSAGE_JOB
    envelope = args[1]
    assert envelope["message"]["id"] == "wamid.123"
    assert envelope["phone_number_id"] == "pn-1"
    assert kwargs["_job_id"] == "whatsapp-ingress:wamid.123"
    assert kwargs["_queue_name"] == QUEUE_NAME


@pytest.mark.asyncio
async def test_enqueuer_raises_if_used_before_connect() -> None:
    enqueuer = MessageEnqueuer.__new__(MessageEnqueuer)
    enqueuer._pool = None

    with pytest.raises(RuntimeError):
        await enqueuer(_context())


def test_context_from_envelope_round_trips_the_enqueued_shape() -> None:
    context = _context()
    envelope = {
        "message": dict(context.message),
        "contacts": [dict(c) for c in context.contacts],
        "phone_number_id": context.phone_number_id,
        "display_phone_number": context.display_phone_number,
    }

    rebuilt = context_from_envelope(envelope)

    assert rebuilt.message == context.message
    assert rebuilt.contacts == context.contacts
    assert rebuilt.phone_number_id == context.phone_number_id
    assert rebuilt.display_phone_number == context.display_phone_number


def test_parse_worker_health_reads_arqs_own_status_line() -> None:
    """This exact format is written by arq.worker.Worker.record_health() --
    admin/queue_router.py depends on parsing it without SSH access, so this
    pins the format assumption."""
    raw = "Aug-08 12:34:56 j_complete=42 j_failed=1 j_retried=2 j_ongoing=0 queued=3"

    health = parse_worker_health(raw)

    assert health is not None
    assert health.jobs_complete == 42
    assert health.jobs_failed == 1
    assert health.jobs_retried == 2
    assert health.jobs_ongoing == 0
    assert health.queue_depth == 3
    assert health.raw == raw


def test_parse_worker_health_returns_none_for_unrecognized_text() -> None:
    """A future ARQ version could change this format -- must degrade to
    'unparseable', not raise, so the admin endpoint can still report the
    worker as alive (see queue_router.py's fallback branch)."""
    assert parse_worker_health("not the format we expect") is None


def test_health_check_key_is_namespaced_under_the_queue_name() -> None:
    # worker.py and admin/queue_router.py both import HEALTH_CHECK_KEY
    # directly rather than deriving it independently -- this just documents
    # the relationship so a change to QUEUE_NAME is obviously also a change
    # to the key both sides read/write.
    assert HEALTH_CHECK_KEY == f"{QUEUE_NAME}:health-check"
