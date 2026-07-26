"""Understanding pipeline foundation tests (M3).

Run entirely against fakes + the in-memory object store — no M2, no docker, no
paid APIs. Proves modality routing, extraction mapping, confidence, correlation
propagation, graceful provider-failure handling, and that missing fields stay
unknown (never fabricated).
"""

from __future__ import annotations

from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import (
    FakeExtractionProvider,
    FakeSpeechProvider,
    FakeTranslationProvider,
    FakeVisionProvider,
)
from mesiri_contracts.assistant import MediaReference, NormalizedMessage
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from understanding.pipeline import UnderstandingPipeline


def _msg(**kwargs) -> NormalizedMessage:
    base = dict(
        message_id="msg_1",
        correlation_id="cor_pipeline",
        modality=InputModality.TEXT,
        sender={"wa_id": "15550001111"},
        timestamp="2026-07-04T10:00:00Z",
    )
    base.update(kwargs)
    return NormalizedMessage.model_validate(base)


async def _build(
    *, speech=None, vision=None, extraction=None, translation=None, storage=None
) -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=speech or FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=vision or FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=extraction or FakeExtractionProvider(fixtures.JCB_EQUIPMENT_EXTRACTION),
        translation=translation or FakeTranslationProvider(),
        object_storage=storage or FakeObjectStorage(),
    )


async def test_malayalam_jcb_voice_yields_equipment_facts():
    storage = FakeObjectStorage()
    await storage.put_object("voice/1.ogg", b"<audio>")
    pipeline = await _build(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        extraction=FakeExtractionProvider(fixtures.JCB_EQUIPMENT_EXTRACTION),
        storage=storage,
    )
    msg = _msg(
        modality=InputModality.VOICE,
        media=MediaReference(object_key="voice/1.ogg", mime_type="audio/ogg"),
    )

    result = await pipeline.understand(msg)

    assert result.semantic_type == SemanticType.EQUIPMENT_USAGE
    facts = result.candidates[0].fields
    assert facts["equipment_name"] == "JCB"
    assert facts["duration_hours"] == 4
    assert result.translated_text == "The JCB ran for 4 hours"
    assert result.overall_confidence == ConfidenceLevel.HIGH
    assert result.correlation_id == "cor_pipeline"
    ops = {e.operation for e in result.provider_executions}
    assert {"speech_to_text_translate", "extract"} <= ops


async def test_receipt_image_yields_expense():
    storage = FakeObjectStorage()
    await storage.put_object("img/1.jpg", b"<image>")
    pipeline = await _build(
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        storage=storage,
    )
    msg = _msg(
        modality=InputModality.IMAGE,
        media=MediaReference(object_key="img/1.jpg", mime_type="image/jpeg"),
    )

    result = await pipeline.understand(msg)
    assert result.semantic_type == SemanticType.EXPENSE
    assert result.candidates[0].fields["amount"] == 1500
    assert result.document_classification == "receipt"


async def test_expense_categories_reach_extraction_for_image():
    """AI-side category selection: the org's real expense_categories names
    must reach the extraction call for an image (receipt photo), not just
    text -- extraction is what actually picks the category field."""
    storage = FakeObjectStorage()
    await storage.put_object("img/1.jpg", b"<image>")
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=extraction,
        storage=storage,
    )
    msg = _msg(
        modality=InputModality.IMAGE,
        media=MediaReference(object_key="img/1.jpg", mime_type="image/jpeg"),
    )

    await pipeline.understand(msg, expense_categories=["Materials", "Fuel"])

    assert extraction.last_expense_categories == ["Materials", "Fuel"]


async def test_expense_categories_reach_extraction_for_text():
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(extraction=extraction)
    msg = _msg(text="spent 250 on cement bags")

    await pipeline.understand(msg, expense_categories=["Materials", "Fuel"])

    assert extraction.last_expense_categories == ["Materials", "Fuel"]


async def test_no_expense_categories_defaults_to_none():
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(extraction=extraction)
    msg = _msg(text="spent 250 on cement bags")

    await pipeline.understand(msg)

    assert extraction.last_expense_categories is None


async def test_partial_receipt_keeps_missing_fields_and_lowers_confidence():
    storage = FakeObjectStorage()
    await storage.put_object("img/2.jpg", b"<image>")
    pipeline = await _build(
        vision=FakeVisionProvider(fixtures.PARTIAL_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.PARTIAL_RECEIPT_EXTRACTION),
        storage=storage,
    )
    msg = _msg(modality=InputModality.IMAGE, media=MediaReference(object_key="img/2.jpg"))
    result = await pipeline.understand(msg)
    assert "vendor" in result.missing_fields
    assert "vendor" not in result.candidates[0].fields
    assert result.overall_confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)


async def test_receipt_raw_fields_reach_extraction_when_description_omits_them():
    """Real bug: Gemini's vision description is a short prose summary that
    does not always restate every field in words (e.g. a receipt described
    as "Restaurant bill for tea and toast" never mentions the total), so
    extraction must still see raw_fields (amount, vendor, ...) through the
    text it's given, or the amount is silently lost between the vision call
    and the extraction call and the user gets asked for it again."""
    storage = FakeObjectStorage()
    await storage.put_object("img/4.jpg", b"<image>")
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(
        vision=FakeVisionProvider(fixtures.RECEIPT_WITHOUT_AMOUNT_IN_DESCRIPTION_VISION),
        extraction=extraction,
        storage=storage,
    )
    msg = _msg(modality=InputModality.IMAGE, media=MediaReference(object_key="img/4.jpg"))

    await pipeline.understand(msg)

    assert "amount: 180" in extraction.last_text
    assert "vendor: Restaurant" in extraction.last_text
    assert "Restaurant bill for tea and toast." in extraction.last_text


async def test_unreadable_image_is_unusable():
    storage = FakeObjectStorage()
    await storage.put_object("img/3.jpg", b"<image>")
    pipeline = await _build(
        vision=FakeVisionProvider(fixtures.UNREADABLE_IMAGE_VISION), storage=storage
    )
    msg = _msg(modality=InputModality.IMAGE, media=MediaReference(object_key="img/3.jpg"))
    result = await pipeline.understand(msg)
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE


async def test_empty_transcript_is_unusable():
    storage = FakeObjectStorage()
    await storage.put_object("voice/2.ogg", b"<audio>")
    pipeline = await _build(
        speech=FakeSpeechProvider(fixtures.EMPTY_TRANSCRIPT_SPEECH), storage=storage
    )
    msg = _msg(modality=InputModality.VOICE, media=MediaReference(object_key="voice/2.ogg"))
    result = await pipeline.understand(msg)
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE
    assert "empty transcript" in result.warnings


async def test_provider_timeout_is_handled_and_observable():
    storage = FakeObjectStorage()
    await storage.put_object("voice/3.ogg", b"<audio>")
    pipeline = await _build(
        speech=FakeSpeechProvider(error=fixtures.timeout_error()), storage=storage
    )
    msg = _msg(modality=InputModality.VOICE, media=MediaReference(object_key="voice/3.ogg"))
    result = await pipeline.understand(msg)
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE
    failed = [e for e in result.provider_executions if not e.succeeded]
    assert failed and failed[0].error_code == "PROVIDER_TIMEOUT"


async def test_provider_unavailable_is_handled():
    pipeline = await _build(extraction=FakeExtractionProvider(error=fixtures.unavailable_error()))
    result = await pipeline.understand(_msg(text="20 bags cement received"))
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE
    assert any(e.error_code == "PROVIDER_UNAVAILABLE" for e in result.provider_executions)


async def test_text_message_extraction():
    pipeline = await _build(extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION))
    result = await pipeline.understand(_msg(text="paid 1500 to ABC Hardware"))
    assert result.semantic_type == SemanticType.EXPENSE
    assert result.normalized_text == "paid 1500 to ABC Hardware"


async def test_empty_text_is_unusable():
    pipeline = await _build()
    result = await pipeline.understand(_msg(text="   "))
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE


async def test_understanding_result_is_schema_valid_and_serializable():
    pipeline = await _build(extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION))
    result = await pipeline.understand(_msg(text="paid 1500"))
    dumped = result.model_dump()
    assert dumped["version"] == "v1"
    assert dumped["correlation_id"] == "cor_pipeline"


async def test_text_greeting_skips_translation_and_extraction():
    """A deterministic "hi" must never depend on an AI provider correctly
    finding no fields -- and should cost nothing while it's at it."""
    translation = FakeTranslationProvider()
    extraction = FakeExtractionProvider()
    pipeline = await _build(translation=translation, extraction=extraction)

    result = await pipeline.understand(_msg(text="hi"))

    assert result.semantic_type == SemanticType.UNKNOWN
    assert result.overall_confidence == ConfidenceLevel.HIGH
    assert result.candidates == []
    assert translation.calls == 0
    assert extraction.calls == 0


async def test_voice_greeting_skips_extraction_after_transcription():
    """STT is unavoidable for voice -- but the extraction call after it is
    not, once the transcript is a recognized greeting."""
    from mesiri_ai.models import SpeechResult

    storage = FakeObjectStorage()
    await storage.put_object("voice/greeting.ogg", b"<audio>")
    extraction = FakeExtractionProvider()
    pipeline = await _build(
        speech=FakeSpeechProvider(SpeechResult(transcript="hi", translated_text="hi")),
        extraction=extraction,
        storage=storage,
    )
    msg = _msg(
        modality=InputModality.VOICE,
        media=MediaReference(object_key="voice/greeting.ogg", mime_type="audio/ogg"),
    )

    result = await pipeline.understand(msg)

    assert result.semantic_type == SemanticType.UNKNOWN
    assert result.overall_confidence == ConfidenceLevel.HIGH
    assert extraction.calls == 0
    # The transcription call itself is never skipped -- there's no text to
    # check against the greeting list before Sarvam produces one.
    ops = {e.operation for e in result.provider_executions}
    assert "speech_to_text_translate" in ops
    assert "extract" not in ops


async def test_a_report_that_merely_mentions_hi_still_gets_extracted():
    """The greeting check requires the whole message to be greeting words --
    real content alongside "hi" must still reach extraction."""
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand(_msg(text="hi, 50 bags of cement arrived"))

    assert extraction.calls == 1
    assert result.semantic_type != SemanticType.UNKNOWN
