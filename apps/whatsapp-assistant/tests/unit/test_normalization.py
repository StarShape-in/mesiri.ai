"""Unit tests for Meta payload normalization."""

from __future__ import annotations

from datetime import UTC, datetime

from ingress.media_ingestion import DownloadedMedia
from ingress.normalization import MessageNormalizer
from mesiri_contracts.assistant import MessageType


def test_normalize_text_message() -> None:
    normalizer = MessageNormalizer()
    message = {
        "from": "919876543210",
        "id": "wamid.text",
        "timestamp": "1710000000",
        "type": "text",
        "text": {"body": "Installed 20 bags of cement"},
    }
    contacts = [{"wa_id": "919876543210", "profile": {"name": "Site Engineer"}}]

    normalized = normalizer.normalize(
        message,
        contacts=contacts,
        phone_number_id="PHONE_NUMBER_ID",
        display_phone_number="15550001111",
    )

    assert normalized.message_id == "wamid.text"
    assert normalized.channel == "whatsapp"
    assert normalized.message_type is MessageType.TEXT
    assert normalized.content == "Installed 20 bags of cement"
    assert normalized.sender.profile_name == "Site Engineer"
    assert normalized.timestamp == datetime.fromtimestamp(1710000000, tz=UTC)


def test_normalize_image_message_with_downloaded_media() -> None:
    normalizer = MessageNormalizer()
    message = {
        "from": "919876543210",
        "id": "wamid.image",
        "timestamp": "1710000001",
        "type": "image",
        "image": {
            "id": "media-image-1",
            "mime_type": "image/jpeg",
            "caption": "Delivery challan",
        },
    }
    downloaded = DownloadedMedia(
        media_id="media-image-1",
        mime_type="image/jpeg",
        file_path="/tmp/media-image-1.jpg",
        sha256="abc123",
        file_size=1024,
    )

    normalized = normalizer.normalize(
        message,
        contacts=[],
        phone_number_id="PHONE_NUMBER_ID",
        display_phone_number="15550001111",
        downloaded_media=downloaded,
    )

    assert normalized.message_type is MessageType.IMAGE
    assert normalized.content == "Delivery challan"
    assert normalized.media is not None
    assert normalized.media.file_path == "/tmp/media-image-1.jpg"


def test_normalize_voice_message() -> None:
    normalizer = MessageNormalizer()
    message = {
        "from": "919876543210",
        "id": "wamid.voice",
        "timestamp": "1710000002",
        "type": "audio",
        "audio": {
            "id": "media-audio-1",
            "mime_type": "audio/ogg; codecs=opus",
            "voice": True,
        },
    }
    downloaded = DownloadedMedia(
        media_id="media-audio-1",
        mime_type="audio/ogg",
        file_path="/tmp/media-audio-1.ogg",
        sha256="voice123",
        file_size=2048,
    )

    normalized = normalizer.normalize(
        message,
        contacts=[],
        phone_number_id="PHONE_NUMBER_ID",
        display_phone_number="15550001111",
        downloaded_media=downloaded,
    )

    assert normalized.message_type is MessageType.VOICE
    assert normalized.media is not None
    assert normalized.media.media_id == "media-audio-1"
