"""Unit tests for the ARQ worker's job function (worker.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ingress.receiver import MessageIngressContext
from worker import process_claimed_message_job


def _envelope() -> dict:
    return {
        "message": {"id": "wamid.123", "from": "15551234567", "type": "text"},
        "contacts": [],
        "phone_number_id": "pn-1",
        "display_phone_number": "+1 555 123 4567",
    }


@pytest.mark.asyncio
async def test_job_raises_when_processing_failed_so_arq_can_retry() -> None:
    """process_claimed_message returning None means _process_message_locked
    caught and logged a failure internally (see ingress/receiver.py) --
    without this re-raise, ARQ would see a cleanly-returned coroutine and
    count the job as successfully completed, never retrying it despite
    max_tries being configured in WorkerSettings."""
    receiver = AsyncMock()
    receiver.process_claimed_message.return_value = None
    container = AsyncMock()
    container.receiver = receiver
    ctx = {"container": container}

    with pytest.raises(RuntimeError, match="wamid.123"):
        await process_claimed_message_job(ctx, _envelope())


@pytest.mark.asyncio
async def test_job_completes_normally_when_processing_succeeded() -> None:
    receiver = AsyncMock()
    receiver.process_claimed_message.return_value = object()  # any non-None result
    container = AsyncMock()
    container.receiver = receiver
    ctx = {"container": container}

    await process_claimed_message_job(ctx, _envelope())

    receiver.process_claimed_message.assert_awaited_once()
    (context,) = receiver.process_claimed_message.await_args.args
    assert isinstance(context, MessageIngressContext)
    assert context.message["id"] == "wamid.123"
