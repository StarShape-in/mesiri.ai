"""Unit tests for Meta payload normalization."""

from __future__ import annotations

from datetime import UTC, datetime

from ingress.normalization import MessageNormalizer
from mesiri_contracts.assistant import MediaReference
from mesiri_contracts.assistant.enums import InputModality


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
    assert normalized.modality is InputModality.TEXT
    assert normalized.text == "Installed 20 bags of cement"
    assert normalized.sender.profile_name == "Site Engineer"
    assert normalized.timestamp == datetime.fromtimestamp(1710000000, tz=UTC)


def test_normalize_image_message_with_media_reference() -> None:
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
    media = MediaReference(
        object_key="media/wamid.image/media-image-1",
        mime_type="image/jpeg",
        size_bytes=1024,
    )

    normalized = normalizer.normalize(
        message,
        contacts=[],
        phone_number_id="PHONE_NUMBER_ID",
        display_phone_number="15550001111",
        media=media,
    )

    assert normalized.modality is InputModality.IMAGE
    assert normalized.text == "Delivery challan"
    assert normalized.media is not None
    assert normalized.media.object_key == "media/wamid.image/media-image-1"


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
    media = MediaReference(
        object_key="media/wamid.voice/media-audio-1",
        mime_type="audio/ogg",
        size_bytes=2048,
    )

    normalized = normalizer.normalize(
        message,
        contacts=[],
        phone_number_id="PHONE_NUMBER_ID",
        display_phone_number="15550001111",
        media=media,
    )

    assert normalized.modality is InputModality.VOICE
    assert normalized.media is not None
    assert normalized.media.object_key == "media/wamid.voice/media-audio-1"
