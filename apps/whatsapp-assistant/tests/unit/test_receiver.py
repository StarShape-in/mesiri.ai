"""Unit tests for WhatsApp ingress receiver orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from tests.fixtures.meta_payloads import (
    image_webhook_payload,
    text_webhook_payload,
    voice_webhook_payload,
)

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import DownloadedMedia
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver
from mesiri_contracts.assistant import MessageType


@pytest.mark.asyncio
async def test_receiver_normalizes_text_message() -> None:
    deduplication_store = InMemoryDeduplicationStore()
    message_store = InMemoryNormalizedMessageStore()
    media_downloader = AsyncMock()
    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
    )

    scheduled = await receiver.handle_payload(text_webhook_payload())
    await receiver.wait_until_idle()

    assert scheduled == 1
    media_downloader.download.assert_not_called()
    normalized = await message_store.get("wamid.text")
    assert normalized is not None
    assert normalized.message_type is MessageType.TEXT


@pytest.mark.asyncio
async def test_receiver_deduplicates_duplicate_webhooks() -> None:
    deduplication_store = InMemoryDeduplicationStore()
    message_store = InMemoryNormalizedMessageStore()
    media_downloader = AsyncMock()
    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
    )

    payload = text_webhook_payload()
    assert await receiver.handle_payload(payload) == 1
    assert await receiver.handle_payload(payload) == 0
    await receiver.wait_until_idle()

    normalized = await message_store.get("wamid.text")
    assert normalized is not None


@pytest.mark.asyncio
async def test_receiver_downloads_media_for_image_and_voice() -> None:
    deduplication_store = InMemoryDeduplicationStore()
    message_store = InMemoryNormalizedMessageStore()
    media_downloader = AsyncMock()
    media_downloader.download.side_effect = [
        DownloadedMedia(
            media_id="media-image-1",
            mime_type="image/jpeg",
            file_path="/tmp/media-image-1.jpg",
            sha256="abc123",
            file_size=1024,
        ),
        DownloadedMedia(
            media_id="media-audio-1",
            mime_type="audio/ogg",
            file_path="/tmp/media-audio-1.ogg",
            sha256="voice123",
            file_size=2048,
        ),
    ]
    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
    )

    image_payload = image_webhook_payload(message_id="wamid.image-1")
    voice_payload = voice_webhook_payload(message_id="wamid.voice-1")

    assert await receiver.handle_payload(image_payload) == 1
    assert await receiver.handle_payload(voice_payload) == 1
    await receiver.wait_until_idle()

    image_message = await message_store.get("wamid.image-1")
    voice_message = await message_store.get("wamid.voice-1")

    assert image_message is not None
    assert image_message.message_type is MessageType.IMAGE
    assert voice_message is not None
    assert voice_message.message_type is MessageType.VOICE
    assert media_downloader.download.await_count == 2
