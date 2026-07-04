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
    """Construct the understanding pipeline.

    Uses the real Sarvam/Gemini adapters when API keys are configured, otherwise
    deterministic fakes so the webhook works end-to-end without paid providers.
    """
    speech: object
    vision: object
    extraction: object

    sarvam_key = os.environ.get("MESIRI_SARVAM__API_KEY")
    gemini_key = os.environ.get("MESIRI_GEMINI__API_KEY")

    if sarvam_key or gemini_key:
        from mesiri.bootstrap.settings import get_settings
        from mesiri_ai.adapters.gemini.adapter import GeminiProvider
        from mesiri_ai.adapters.sarvam.adapter import SarvamSpeechProvider

        settings = get_settings()
        gemini = GeminiProvider(settings.gemini)
        speech = SarvamSpeechProvider(settings.sarvam) if sarvam_key else FakeSpeechProvider(
            fixtures.MALAYALAM_JCB_SPEECH
        )
        vision = gemini if gemini_key else FakeVisionProvider(fixtures.VALID_RECEIPT_VISION)
        extraction = gemini if gemini_key else FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
        logger.info("Understanding pipeline using real providers (sarvam=%s gemini=%s)",
                    bool(sarvam_key), bool(gemini_key))
    else:
        speech = FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH)
        vision = FakeVisionProvider(fixtures.VALID_RECEIPT_VISION)
        extraction = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
        logger.info("Understanding pipeline using FAKE providers (no AI keys configured)")

    return UnderstandingPipeline(
        speech=speech,  # type: ignore[arg-type]
        vision=vision,  # type: ignore[arg-type]
        extraction=extraction,  # type: ignore[arg-type]
        object_storage=object_storage,
        confidence_policy=ConfidencePolicy(),
    )


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
