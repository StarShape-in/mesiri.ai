"""M2 -> M3 boundary adapter and pipeline factory.

The canonical ``NormalizedMessage`` (M2, Alan) and the understanding pipeline's
input differ in a few field names/representations (see
``docs/execution/M2_M3_INTEGRATION_GAP.md``). This module holds the single,
explicit, documented mapping between them — not glue hidden across the codebase.

It also performs the media handoff: M2 downloads media to a local ``file_path``;
here we place those bytes behind the ObjectStorage boundary and hand M3 an
``object_key`` (M3 never reads the local path directly).
"""

from __future__ import annotations

import logging
import os

from mesiri_ai.confidence import ConfidencePolicy
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_ai import fixtures
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import MessageType, NormalizedMessage
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.storage import ObjectStoragePort

from .inbound import MediaReference, NormalizedMessageRef, ReplyContext
from .pipeline import UnderstandingPipeline

logger = logging.getLogger(__name__)

_MODALITY_BY_TYPE = {
    MessageType.TEXT: InputModality.TEXT,
    MessageType.IMAGE: InputModality.IMAGE,
    MessageType.VOICE: InputModality.VOICE,
}


async def to_reading_model(
    message: NormalizedMessage,
    object_storage: ObjectStoragePort,
) -> NormalizedMessageRef:
    """Map a canonical NormalizedMessage to the M3 pipeline input.

    If the message carries media with a local ``file_path`` (and no object key
    yet), the bytes are pushed to object storage and referenced by key.
    """
    media_ref: MediaReference | None = None
    if message.media is not None:
        object_key = message.media.object_key
        if object_key is None and message.media.file_path and os.path.exists(message.media.file_path):
            object_key = f"media/{message.message_id}/{message.media.media_id}"
            with open(message.media.file_path, "rb") as fh:
                data = fh.read()
            await object_storage.put_object(object_key, data, content_type=message.media.mime_type)
        media_ref = MediaReference(
            object_key=object_key or f"media/{message.message_id}/{message.media.media_id}",
            mime_type=message.media.mime_type,
            size_bytes=message.media.file_size,
        )

    reply = (
        ReplyContext(replied_to_message_id=message.reply_to) if message.reply_to else None
    )

    return NormalizedMessageRef(
        message_id=message.message_id,
        external_message_id=message.message_id,
        correlation_id=message.correlation_id,
        timestamp=message.timestamp.isoformat(),
        modality=_MODALITY_BY_TYPE.get(message.message_type, InputModality.UNKNOWN),
        text=message.content,
        media=media_ref,
        reply_context=reply,
    )


def build_pipeline(object_storage: ObjectStoragePort) -> UnderstandingPipeline:
    """Construct the understanding pipeline from configured providers.

    Sarvam -> voice; DeepSeek -> text/transcript extraction; Gemini -> vision
    (images). Any provider without a configured key falls back to a deterministic
    fake so the webhook still works end to end.
    """
    from mesiri.bootstrap.settings import get_settings

    settings = get_settings()

    # Speech (voice)
    if settings.sarvam.api_key:
        from mesiri_ai.adapters.sarvam.adapter import SarvamSpeechProvider

        speech: object = SarvamSpeechProvider(settings.sarvam)
    else:
        speech = FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH)

    # Structured extraction (text + transcripts)
    if settings.deepseek.api_key:
        from mesiri_ai.adapters.deepseek.adapter import DeepSeekExtractionProvider

        extraction: object = DeepSeekExtractionProvider(settings.deepseek)
    elif settings.gemini.api_key:
        from mesiri_ai.adapters.gemini.adapter import GeminiProvider

        extraction = GeminiProvider(settings.gemini)
    else:
        extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)

    # Vision (images) — DeepSeek has no vision; use Gemini if available.
    if settings.gemini.api_key:
        from mesiri_ai.adapters.gemini.adapter import GeminiProvider

        vision: object = GeminiProvider(settings.gemini)
    else:
        vision = FakeVisionProvider(fixtures.VALID_RECEIPT_VISION)

    logger.info(
        "Understanding pipeline: speech=%s extraction=%s vision=%s",
        type(speech).__name__, type(extraction).__name__, type(vision).__name__,
    )
    return UnderstandingPipeline(
        speech=speech,  # type: ignore[arg-type]
        vision=vision,  # type: ignore[arg-type]
        extraction=extraction,  # type: ignore[arg-type]
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


async def understand(
    message: NormalizedMessage,
    pipeline: UnderstandingPipeline,
    object_storage: ObjectStoragePort,
) -> UnderstandingResult:
    """Run the full M2 message through M3 understanding."""
    ref = await to_reading_model(message, object_storage)
    result = await pipeline.understand(ref)
    logger.info(
        "understanding.complete message=%s correlation=%s semantic=%s confidence=%s",
        result.source_message_id,
        result.correlation_id,
        result.semantic_type.value,
        result.overall_confidence.value,
    )
    return result
