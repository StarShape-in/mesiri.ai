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
    FakeVisionProvider,
    FakeVoiceExtractionProvider,
)
from mesiri_ai.models import ExtractionResult
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
    *, voice_extraction=None, vision=None, extraction=None, storage=None
) -> UnderstandingPipeline:
    return UnderstandingPipeline(
        voice_extraction=voice_extraction
        or FakeVoiceExtractionProvider(fixtures.MALAYALAM_JCB_VOICE_EXTRACTION),
        vision=vision or FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=extraction or FakeExtractionProvider(fixtures.JCB_EQUIPMENT_EXTRACTION),
        object_storage=storage or FakeObjectStorage(),
    )


async def test_malayalam_jcb_voice_yields_equipment_facts():
    storage = FakeObjectStorage()
    await storage.put_object("voice/1.ogg", b"<audio>")
    pipeline = await _build(
        voice_extraction=FakeVoiceExtractionProvider(fixtures.MALAYALAM_JCB_VOICE_EXTRACTION),
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
    # One merged call now, not a separate speech_to_text_translate + extract
    # pair -- see ports/voice_extraction.py.
    ops = {e.operation for e in result.provider_executions}
    assert ops == {"understand_voice"}


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
        voice_extraction=FakeVoiceExtractionProvider(
            ExtractionResult(transcript="", translated_text="")
        ),
        storage=storage,
    )
    msg = _msg(modality=InputModality.VOICE, media=MediaReference(object_key="voice/2.ogg"))
    result = await pipeline.understand(msg)
    assert result.overall_confidence == ConfidenceLevel.UNUSABLE
    assert "empty transcript" in result.warnings


async def test_provider_timeout_is_handled_and_observable():
    storage = FakeObjectStorage()
    await storage.put_object("voice/3.ogg", b"<audio>")
    pipeline = await _build(
        voice_extraction=FakeVoiceExtractionProvider(error=fixtures.timeout_error()),
        storage=storage,
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


async def test_text_greeting_skips_extraction():
    """A deterministic "hi" must never depend on an AI provider correctly
    finding no fields -- and should cost nothing while it's at it."""
    extraction = FakeExtractionProvider()
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand(_msg(text="hi"))

    assert result.semantic_type == SemanticType.UNKNOWN
    assert result.overall_confidence == ConfidenceLevel.HIGH
    assert result.candidates == []
    assert extraction.calls == 0


async def test_voice_greeting_is_understood_via_the_single_merged_call():
    """A spoken "hi" used to skip a *second* call (extraction) after
    transcription -- that shortcut no longer exists once transcribe+extract
    are merged into one call (see ports/voice_extraction.py and pipeline.py's
    _handle_voice): there's no cheap first call left to check the transcript
    against the greeting list before deciding whether to spend the second
    one. A greeting now costs the same one call as everything else, and
    must still come back correctly classified and HIGH-confidence via
    ordinary extraction's own "unknown" semantic_type -- not a deterministic
    shortcut."""
    voice_extraction = FakeVoiceExtractionProvider(
        ExtractionResult(transcript="hi", translated_text="hi", semantic_type="unknown")
    )
    storage = FakeObjectStorage()
    await storage.put_object("voice/greeting.ogg", b"<audio>")
    pipeline = await _build(voice_extraction=voice_extraction, storage=storage)
    msg = _msg(
        modality=InputModality.VOICE,
        media=MediaReference(object_key="voice/greeting.ogg"),
    )

    result = await pipeline.understand(msg)

    assert result.semantic_type == SemanticType.UNKNOWN
    assert result.overall_confidence == ConfidenceLevel.HIGH
    assert voice_extraction.calls == 1
    ops = {e.operation for e in result.provider_executions}
    assert ops == {"understand_voice"}


async def test_a_report_that_merely_mentions_hi_still_gets_extracted():
    """The greeting check requires the whole message to be greeting words --
    real content alongside "hi" must still reach extraction."""
    extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand(_msg(text="hi, 50 bags of cement arrived"))

    assert extraction.calls == 1
    assert result.semantic_type != SemanticType.UNKNOWN


async def test_understand_text_segment_classifies_one_decomposed_segment():
    """docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9: a segment already
    split out of a multi-intent message goes through the same extract() +
    _apply_extraction path an ordinary message does, just called directly
    on the segment's own text rather than through understand()."""
    extraction = FakeExtractionProvider(
        ExtractionResult(
            semantic_type="project_create",
            fields={"name": "Starship"},
            provider="fake",
            model="fake-model",
            latency_ms=12.0,
        )
    )
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand_text_segment(
        "create a project called Starship",
        source_message_id="msg_1",
        correlation_id="cor_1",
    )

    assert result.semantic_type == SemanticType.PROJECT_CREATE
    assert result.candidates[0].fields["name"] == "Starship"
    assert result.transcript == "create a project called Starship"
    assert result.normalized_text == "create a project called Starship"
    assert result.correlation_id == "cor_1"
    assert result.source_message_id == "msg_1"
    assert result.input_modality == InputModality.TEXT
    assert extraction.calls == 1


async def test_understand_text_segment_skips_the_greeting_shortcut():
    """A bare "hi" as its own segment must still reach extraction -- the
    deterministic greeting shortcut is understand()'s pre-pipeline check,
    not something a segment (which the decomposer already judged to be
    part of an actionable multi-intent message) should re-trigger."""
    extraction = FakeExtractionProvider(
        ExtractionResult(semantic_type="unknown", provider="fake", model="fake-model")
    )
    pipeline = await _build(extraction=extraction)

    await pipeline.understand_text_segment(
        "hi", source_message_id="msg_1", correlation_id="cor_1"
    )

    assert extraction.calls == 1


async def test_understand_text_segment_passes_expense_categories_through():
    extraction = FakeExtractionProvider(
        ExtractionResult(semantic_type="expense", fields={"amount": 500}, provider="fake")
    )
    pipeline = await _build(extraction=extraction)

    await pipeline.understand_text_segment(
        "paid 500 to the hardware store",
        source_message_id="msg_1",
        correlation_id="cor_1",
        expense_categories=["Materials", "Fuel"],
    )

    assert extraction.last_expense_categories == ["Materials", "Fuel"]


# ---------------------------------------------------------------------------
# UnderstandingResult.intents (Phase B2 of docs/execution/
# UNIFIED_UNDERSTANDING_PIPELINE.md) -- always length 1 until B4 changes the
# extraction prompt, but must already be populated correctly, independent of
# `candidates` (a different axis -- see ADR-U3).
# ---------------------------------------------------------------------------


async def test_extraction_populates_intents_alongside_candidates():
    extraction = FakeExtractionProvider(
        ExtractionResult(
            semantic_type="expense", fields={"amount": 500, "vendor": "ABC"}, provider="fake"
        )
    )
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand(_msg(text="paid 500 to ABC"))

    assert len(result.intents) == 1
    assert result.intents[0].semantic_type == SemanticType.EXPENSE
    assert result.intents[0].fields == {"amount": 500, "vendor": "ABC"}
    # candidates (the competing-interpretations axis) still populated
    # exactly as before -- unaffected by adding intents.
    assert len(result.candidates) == 1
    assert result.candidates[0].semantic_type == SemanticType.EXPENSE


async def test_deterministic_greeting_shortcut_still_populates_one_intent():
    """No extraction call happens for a deterministic "hi" -- intents must
    still never be empty (the same invariant B1 enforces on
    ExtractionResult itself)."""
    pipeline = await _build()

    result = await pipeline.understand(_msg(text="hi"))

    assert len(result.intents) == 1
    assert result.intents[0].semantic_type == SemanticType.UNKNOWN


async def test_intents_reflects_unknown_fields_and_missing_fields_per_intent():
    extraction = FakeExtractionProvider(
        ExtractionResult(
            semantic_type="material_update",
            fields={"material_name": "cement"},
            unknown_fields={"batch_no": "X1"},
            missing_fields=["quantity"],
            provider="fake",
        )
    )
    pipeline = await _build(extraction=extraction)

    result = await pipeline.understand(_msg(text="cement batch X1"))

    assert result.intents[0].unknown_fields == {"batch_no": "X1"}
    assert result.intents[0].missing_fields == ["quantity"]
