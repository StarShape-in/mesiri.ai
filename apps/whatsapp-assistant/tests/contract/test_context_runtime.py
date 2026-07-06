"""Runtime integration: NormalizedMessage → Understanding → Context → reply."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx

from context.runtime import build_context_resolver
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.context import ResolvedContext
from runtime.dependencies import Settings, build_container
from runtime.inbound_journey import process_inbound_message
from understanding.pipeline import UnderstandingPipeline
from understanding.runtime import format_reply


def _message(**kwargs) -> NormalizedMessage:
    base = dict(
        message_id="wamid.context.1",
        correlation_id="cor_context_1",
        sender=SenderInfo(wa_id="919876543210", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 6, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="paid 1500 to ABC Hardware",
    )
    base.update(kwargs)
    return NormalizedMessage(**base)


def _pipeline() -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        object_storage=FakeObjectStorage(),
    )


async def test_inbound_journey_produces_resolved_context():
    message = _message()
    pipeline = _pipeline()
    context_resolver = build_context_resolver()
    sent_replies: list[str] = []

    async def capture_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        sent_replies.append(format_reply(understanding))

    understanding, resolved = await process_inbound_message(
        message,
        pipeline=pipeline,
        context_resolver=context_resolver,
        reply_sender=capture_reply,
    )

    assert isinstance(understanding, UnderstandingResult)
    assert isinstance(resolved, ResolvedContext)
    ResolvedContext.model_validate(resolved.model_dump())
    assert resolved.correlation_id == message.correlation_id
    assert resolved.source_message_id == message.message_id
    assert len(sent_replies) == 1


async def test_inbound_journey_reply_unchanged_by_context():
    message = _message()
    pipeline = _pipeline()
    context_resolver = build_context_resolver()

    understanding_only = await pipeline.understand(message)
    expected_reply = format_reply(understanding_only)

    captured: list[str] = []

    async def capture_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        captured.append(format_reply(understanding))

    await process_inbound_message(
        message,
        pipeline=pipeline,
        context_resolver=context_resolver,
        reply_sender=capture_reply,
    )

    assert captured == [expected_reply]


async def test_build_container_wires_context_resolver(tmp_path):
    settings = Settings(
        verify_token="test-verify-token",
        app_secret="test-app-secret",
        access_token="test-access-token",
        media_download_dir=str(tmp_path / "media"),
    )
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        container = build_container(settings, http_client)

    assert container.contract_context_resolver is not None


async def test_context_debug_logs_resolved_context(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="context.runtime")
    message = _message()

    async def noop_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        return None

    await process_inbound_message(
        message,
        pipeline=_pipeline(),
        context_resolver=build_context_resolver(),
        reply_sender=noop_reply,
        context_debug=True,
    )

    assert any("ResolvedContext correlation_id=cor_context_1" in record.message for record in caplog.records)


async def test_reply_sender_receives_same_understanding_as_format_reply():
    message = _message()
    pipeline = _pipeline()
    understanding = await pipeline.understand(message)
    expected_reply = format_reply(understanding)

    sender = AsyncMock()

    async def _send_understanding_reply(msg, result) -> None:
        await sender.send_text(msg.sender.wa_id, format_reply(result))

    await process_inbound_message(
        message,
        pipeline=pipeline,
        context_resolver=build_context_resolver(),
        reply_sender=_send_understanding_reply,
    )

    sender.send_text.assert_awaited_once_with(message.sender.wa_id, expected_reply)
