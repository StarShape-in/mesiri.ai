"""M2 -> M3 contract tests: shared NormalizedMessage through understanding."""

from __future__ import annotations

from datetime import UTC, datetime

from ingress.media_handoff import upload_downloaded_media
from ingress.media_ingestion import DownloadedMedia
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import (
    FakeExtractionProvider,
    FakeSpeechProvider,
    FakeTranslationProvider,
    FakeVisionProvider,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    NormalizedMessage,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from understanding.pipeline import UnderstandingPipeline


def _pipeline(storage: FakeObjectStorage) -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        translation=FakeTranslationProvider(),
        object_storage=storage,
    )


def _msg(**kw) -> NormalizedMessage:
    base = dict(
        message_id="wamid.1",
        sender=SenderInfo(wa_id="15550001111"),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="paid 1500 to ABC Hardware",
    )
    base.update(kw)
    return NormalizedMessage(**base)


async def test_text_message_understands_directly():
    storage = FakeObjectStorage()
    msg = _msg(correlation_id="cor_wire_1")
    result = await _pipeline(storage).understand(msg)
    assert isinstance(result, UnderstandingResult)
    UnderstandingResult.model_validate(result.model_dump())
    assert result.correlation_id == "cor_wire_1"
    assert result.input_modality == InputModality.TEXT
    assert result.normalized_text == "paid 1500 to ABC Hardware"


async def test_normalized_message_has_default_correlation_id():
    assert _msg().correlation_id.startswith("cor_")


async def test_media_upload_populates_object_key_before_m3(tmp_path):
    media_file = tmp_path / "receipt.jpg"
    media_file.write_bytes(b"\xff\xd8fake-jpeg")
    storage = FakeObjectStorage()
    downloaded = DownloadedMedia(
        media_id="m1",
        mime_type="image/jpeg",
        file_path=str(media_file),
        sha256="abc",
        file_size=len(b"\xff\xd8fake-jpeg"),
    )
    media = await upload_downloaded_media(
        message_id="wamid.1",
        downloaded=downloaded,
        object_storage=storage,
    )
    msg = _msg(
        modality=InputModality.IMAGE,
        text=None,
        media=media,
        correlation_id="cor_img_1",
    )
    result = await _pipeline(storage).understand(msg)
    assert result.correlation_id == "cor_img_1"
    assert result.document_classification == "receipt"
    stored = await storage.get_object(media.object_key)
    assert stored.data == b"\xff\xd8fake-jpeg"
