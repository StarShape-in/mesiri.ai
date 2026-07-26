"""Understanding pipeline runtime wiring and reply formatting."""

from __future__ import annotations

import logging
from typing import Any

from mesiri_ai.confidence import ConfidencePolicy
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.storage import ObjectStoragePort
from understanding.pipeline import UnderstandingPipeline

logger = logging.getLogger(__name__)


def build_pipeline(
    object_storage: ObjectStoragePort, db: Any, redis_client: Any
) -> UnderstandingPipeline:
    """Construct the understanding pipeline from configured providers."""
    from mesiri.bootstrap.settings import get_settings
    from mesiri_ai.resolver import DynamicAIProviderResolver

    settings = get_settings()

    resolver = DynamicAIProviderResolver(db, redis_client, settings)

    logger.info("Understanding pipeline configured with DynamicAIProviderResolver proxy.")
    return UnderstandingPipeline(
        speech=resolver,  # type: ignore[arg-type]
        vision=resolver,  # type: ignore[arg-type]
        extraction=resolver,  # type: ignore[arg-type]
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
