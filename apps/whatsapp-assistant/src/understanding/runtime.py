"""Understanding pipeline runtime wiring and reply formatting."""

from __future__ import annotations

import logging

from mesiri_ai import fixtures
from mesiri_ai.confidence import ConfidencePolicy
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.storage import ObjectStoragePort
from understanding.pipeline import UnderstandingPipeline

logger = logging.getLogger(__name__)


def build_pipeline(object_storage: ObjectStoragePort) -> UnderstandingPipeline:
    """Construct the understanding pipeline from configured providers."""
    from mesiri.bootstrap.settings import get_settings

    settings = get_settings()

    if settings.sarvam.api_key:
        from mesiri_ai.adapters.sarvam.adapter import SarvamSpeechProvider

        speech: object = SarvamSpeechProvider(settings.sarvam)
    else:
        speech = FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH)

    if settings.deepseek.api_key:
        from mesiri_ai.adapters.deepseek.adapter import DeepSeekExtractionProvider

        extraction: object = DeepSeekExtractionProvider(settings.deepseek)
    elif settings.gemini.api_key:
        from mesiri_ai.adapters.gemini.adapter import GeminiProvider

        extraction = GeminiProvider(settings.gemini)
    else:
        extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)

    if settings.gemini.api_key:
        from mesiri_ai.adapters.gemini.adapter import GeminiProvider

        vision: object = GeminiProvider(settings.gemini)
        translation: object = GeminiProvider(settings.gemini)
    else:
        from mesiri_ai.fakes import FakeTranslationProvider

        vision = FakeVisionProvider(fixtures.VALID_RECEIPT_VISION)
        translation = FakeTranslationProvider()

    logger.info(
        "Understanding pipeline: speech=%s extraction=%s vision=%s",
        type(speech).__name__,
        type(extraction).__name__,
        type(vision).__name__,
    )
    return UnderstandingPipeline(
        speech=speech,  # type: ignore[arg-type]
        vision=vision,  # type: ignore[arg-type]
        extraction=extraction,  # type: ignore[arg-type]
        translation=translation,  # type: ignore[arg-type]
        object_storage=object_storage,
        confidence_policy=ConfidencePolicy(),
    )


def format_reply(result: UnderstandingResult) -> str:
    """Render the structured understanding result as a WhatsApp reply."""
    lines = ["*Mesiri — understood your message*", ""]
    if result.transcript:
        lines.append(f"🗣 Transcript: {result.transcript}")
    if result.translated_text and result.translated_text != result.transcript:
        lines.append(f"🌐 Translation: {result.translated_text}")
    if result.document_classification:
        lines.append(f"📄 Document: {result.document_classification}")
    lines.append(f"🏷 Type: {result.semantic_type.value}")

    candidate_fields: dict = result.candidates[0].fields if result.candidates else {}
    if candidate_fields:
        lines.append("📋 Details:")
        for key, value in candidate_fields.items():
            lines.append(f"   • {key}: {value}")
    if result.missing_fields:
        lines.append(f"❓ Missing: {', '.join(result.missing_fields)}")
    lines.append(f"✅ Confidence: {result.overall_confidence.value}")
    return "\n".join(lines)
