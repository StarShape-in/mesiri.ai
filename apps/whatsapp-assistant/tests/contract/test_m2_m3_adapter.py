"""M2 -> M3 adapter tests: canonical NormalizedMessage through understanding.

Proves the reconciled contract works: Alan's NormalizedMessage (content,
message_type, media.file_path, correlation_id) maps cleanly into the pipeline and
yields a schema-valid UnderstandingResult with the correlation id preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone

from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    MediaInfo,
    MessageType,
    NormalizedMessage,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult

from understanding.adapter import to_reading_model, understand
from understanding.pipeline import UnderstandingPipeline


def _pipeline(storage: FakeObjectStorage) -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        object_storage=storage,
    )


def _msg(**kw) -> NormalizedMessage:
    base = dict(
        message_id="wamid.1",
        sender=SenderInfo(wa_id="15550001111"),
        timestamp=datetime.now(timezone.utc),
        message_type=MessageType.TEXT,
        content="paid 1500 to ABC Hardware",
    )
    base.update(kw)
    return NormalizedMessage(**base)


async def test_text_message_maps_and_understands():
    storage = FakeObjectStorage()
    msg = _msg(correlation_id="cor_wire_1")
    result = await understand(msg, _pipeline(storage), storage)
    assert isinstance(result, UnderstandingResult)
    UnderstandingResult.model_validate(result.model_dump())
    assert result.correlation_id == "cor_wire_1"          # propagated from M2
    assert result.input_modality == InputModality.TEXT
    assert result.normalized_text == "paid 1500 to ABC Hardware"


async def test_normalized_message_has_default_correlation_id():
    # The contract fix: correlation_id is first-class with a default.
    assert _msg().correlation_id.startswith("cor_")


async def test_media_file_is_pushed_to_object_storage(tmp_path):
    media_file = tmp_path / "receipt.jpg"
    media_file.write_bytes(b"\xff\xd8fake-jpeg")
    storage = FakeObjectStorage()
    msg = _msg(
        message_type=MessageType.IMAGE,
        content=None,
        media=MediaInfo(media_id="m1", mime_type="image/jpeg", file_path=str(media_file)),
    )
    ref = await to_reading_model(msg, storage)
    assert ref.media is not None and ref.media.object_key
    # The bytes are now behind the ObjectStorage boundary (not read via file_path).
    stored = await storage.get_object(ref.media.object_key)
    assert stored.data == b"\xff\xd8fake-jpeg"


async def test_image_message_understands_via_object_storage(tmp_path):
    media_file = tmp_path / "receipt.jpg"
    media_file.write_bytes(b"\xff\xd8fake-jpeg")
    storage = FakeObjectStorage()
    msg = _msg(
        message_type=MessageType.IMAGE,
        content=None,
        media=MediaInfo(media_id="m1", mime_type="image/jpeg", file_path=str(media_file)),
        correlation_id="cor_img_1",
    )
    result = await understand(msg, _pipeline(storage), storage)
    assert result.correlation_id == "cor_img_1"
    assert result.document_classification == "receipt"
