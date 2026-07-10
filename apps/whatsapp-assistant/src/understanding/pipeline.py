"""Understanding pipeline (M3).

Consumes ``NormalizedMessage.v1`` and produces ``UnderstandingResult.v1``:

    text/interactive -> extraction
    voice            -> speech (STT + translation) -> extraction
    image/document   -> vision -> extraction

Providers are injected via their ports (never SDKs), media is read through the
M0 object-storage abstraction (never R2 directly), and confidence is scored by
the deterministic policy. Provider failures are caught and surfaced as an
UNUSABLE result with observable telemetry rather than crashing the pipeline.

This module performs NO business persistence, context resolution, or workflow
selection (Understanding Module Boundary).
"""

from __future__ import annotations

from typing import Any

from mesiri_ai.confidence import ConfidencePolicy, ConfidenceSignals
from mesiri_ai.models import ExtractionResult
from mesiri_ai.ports.extraction import StructuredExtractionProvider
from mesiri_ai.ports.speech import SpeechUnderstandingProvider
from mesiri_ai.ports.translation import TranslationProvider
from mesiri_ai.ports.vision import VisionUnderstandingProvider
from mesiri_contracts.assistant.candidates import CANDIDATE_TYPES, Candidate, FieldConfidence
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.understanding_result import ProviderExecution, UnderstandingResult
from mesiri_contracts.common.errors import ErrorCategory, MesiriError
from mesiri_contracts.common.storage import ObjectStoragePort

# Minimal required-field expectations per semantic type (drives confidence).
_REQUIRED_FIELDS: dict[SemanticType, tuple[str, ...]] = {
    SemanticType.EXPENSE: ("amount",),
    SemanticType.EQUIPMENT_USAGE: ("equipment_name", "duration_hours"),
    SemanticType.MATERIAL_UPDATE: ("material_name",),
    SemanticType.LABOUR_UPDATE: ("headcount",),
    SemanticType.GENERAL_SITE_UPDATE: (),
    SemanticType.GENERAL_QUESTION: (),
    SemanticType.UNKNOWN: (),
}


class UnderstandingPipeline:
    def __init__(
        self,
        *,
        speech: SpeechUnderstandingProvider,
        vision: VisionUnderstandingProvider,
        extraction: StructuredExtractionProvider,
        translation: TranslationProvider,
        object_storage: ObjectStoragePort,
        confidence_policy: ConfidencePolicy | None = None,
    ) -> None:
        self._speech = speech
        self._vision = vision
        self._extraction = extraction
        self._translation = translation
        self._storage = object_storage
        self._confidence = confidence_policy or ConfidencePolicy()

    async def understand(self, message: NormalizedMessage) -> UnderstandingResult:
        result = UnderstandingResult(
            source_message_id=message.message_id,
            correlation_id=message.correlation_id,
            input_modality=message.modality,
            original_content_reference=message.media.object_key if message.media else None,
        )
        try:
            if message.modality in (InputModality.TEXT, InputModality.INTERACTIVE):
                await self._handle_text(message, result)
            elif message.modality == InputModality.VOICE:
                await self._handle_voice(message, result)
            elif message.modality in (InputModality.IMAGE, InputModality.DOCUMENT):
                await self._handle_image(message, result)
            else:
                result.warnings.append(f"unsupported modality: {message.modality.value}")
                result.overall_confidence = ConfidenceLevel.UNUSABLE
        except MesiriError as err:
            result.warnings.append(err.user_safe_message)
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.provider_executions.append(
                ProviderExecution(
                    provider=str(err.details.get("provider", "pipeline")),
                    operation="understand",
                    succeeded=False,
                    error_code=err.error_code,
                )
            )
        return result

    async def _handle_text(self, message: NormalizedMessage, result: UnderstandingResult) -> None:
        text = (message.text or "").strip()
        if not text:
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.warnings.append("empty text")
            return

        result.transcript = text

        translation = await self._translation.translate_to_english(
            text, correlation_id=result.correlation_id
        )
        result.translated_text = translation.translated_text
        result.detected_language = translation.detected_language
        result.normalized_text = translation.translated_text or text

        result.provider_executions.append(
            ProviderExecution(
                provider=getattr(self._translation, "provider", "unknown"),
                operation="translate",
                model=translation.model,
                latency_ms=translation.latency_ms,
            )
        )

        extraction = await self._extraction.extract(
            result.normalized_text, correlation_id=result.correlation_id
        )
        self._apply_extraction(result, extraction, is_empty=False)

    async def _handle_voice(self, message: NormalizedMessage, result: UnderstandingResult) -> None:
        audio = await self._read_media(message)
        speech = await self._speech.transcribe(audio, correlation_id=result.correlation_id)
        result.transcript = speech.transcript
        result.detected_language = speech.detected_language
        result.translated_text = speech.translated_text
        result.normalized_text = speech.translated_text or speech.transcript
        result.provider_executions.append(
            ProviderExecution(
                provider="sarvam",
                operation="speech_to_text_translate",
                model=speech.model,
                latency_ms=speech.latency_ms,
            )
        )
        if not (result.normalized_text or "").strip():
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.warnings.append("empty transcript")
            return
        extraction = await self._extraction.extract(
            result.normalized_text, correlation_id=result.correlation_id
        )
        self._apply_extraction(result, extraction, is_empty=False)

    async def _handle_image(self, message: NormalizedMessage, result: UnderstandingResult) -> None:
        image = await self._read_media(message)
        mime = message.media.mime_type if message.media else None
        vision = await self._vision.analyze_image(
            image, mime_type=mime, correlation_id=result.correlation_id
        )
        result.document_classification = vision.document_classification
        result.normalized_text = vision.description
        result.provider_executions.append(
            ProviderExecution(
                provider="gemini",
                operation="analyze_image",
                model=vision.model,
                latency_ms=vision.latency_ms,
            )
        )
        unreadable = (
            vision.document_classification or ""
        ).lower() == "unknown" and not vision.raw_fields
        if unreadable:
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.warnings.append("image not interpretable")
            return
        source = vision.description or str(vision.raw_fields)
        extraction = await self._extraction.extract(source, correlation_id=result.correlation_id)
        self._apply_extraction(result, extraction, is_empty=False)

    async def _read_media(self, message: NormalizedMessage) -> bytes:
        if message.media is None:
            raise MesiriError(
                error_code="VALIDATION_ERROR",
                category=ErrorCategory.VALIDATION,
                internal_message="media modality without a media reference",
                correlation_id=message.correlation_id,
            )
        obj = await self._storage.get_object(message.media.object_key)
        return obj.data

    def _apply_extraction(
        self, result: UnderstandingResult, extraction: ExtractionResult, *, is_empty: bool
    ) -> None:
        try:
            semantic = SemanticType(extraction.semantic_type)
        except ValueError:
            semantic = SemanticType.UNKNOWN
        result.semantic_type = semantic

        candidate = self._build_candidate(semantic, extraction)
        result.candidates.append(candidate)
        result.missing_fields = list(extraction.missing_fields)
        result.warnings.extend(extraction.warnings)
        result.provider_executions.append(
            ProviderExecution(
                provider=getattr(self._extraction, "provider", "unknown"),
                operation="extract",
                model=extraction.model,
                latency_ms=extraction.latency_ms,
            )
        )

        required = _REQUIRED_FIELDS.get(semantic, ())
        signals = ConfidenceSignals(
            provider_succeeded=True,
            schema_valid=True,
            is_empty=is_empty,
            required_fields=required,
            present_fields=tuple(extraction.fields.keys()),
            missing_fields=tuple(extraction.missing_fields),
            field_confidences=tuple(extraction.field_confidences.values()),
        )
        result.overall_confidence = self._confidence.evaluate(signals)

    @staticmethod
    def _build_candidate(semantic: SemanticType, extraction: ExtractionResult) -> Candidate:
        candidate_cls = CANDIDATE_TYPES.get(semantic, Candidate)
        field_confidences = [
            FieldConfidence(field=k, confidence=v) for k, v in extraction.field_confidences.items()
        ]
        kwargs: dict[str, Any] = dict(
            fields=extraction.fields,
            unknown_fields=extraction.unknown_fields,
            missing_fields=extraction.missing_fields,
            field_confidences=field_confidences,
            warnings=extraction.warnings,
        )
        if candidate_cls is Candidate:
            kwargs["semantic_type"] = semantic
        return candidate_cls(**kwargs)
