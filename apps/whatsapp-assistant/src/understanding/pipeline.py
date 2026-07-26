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

import json
from typing import Any

from mesiri_ai.confidence import ConfidencePolicy, ConfidenceSignals
from mesiri_ai.greeting_classifier import is_greeting_trigger
from mesiri_ai.models import ExtractionResult
from mesiri_ai.ports.extraction import StructuredExtractionProvider
from mesiri_ai.ports.speech import SpeechUnderstandingProvider
from mesiri_ai.ports.vision import VisionUnderstandingProvider
from mesiri_ai.whoami_classifier import is_whoami_trigger
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
    # Confidence is judged on the provider's own output, before
    # canonicalization folds the shapes together -- so this names what the
    # extraction prompt actually asks for (`workers`). A provider that falls
    # back to a flat `headcount` still canonicalizes fine (see
    # canonicalization/builder._normalize_labour_fields); it just scores as
    # one missing field, which is honest -- that reply lost the names.
    SemanticType.LABOUR_UPDATE: ("workers",),
    SemanticType.GENERAL_SITE_UPDATE: (),
    SemanticType.GENERAL_QUESTION: (),
    SemanticType.WHOAMI_QUESTION: (),
    SemanticType.INVENTORY_QUERY: (),
    SemanticType.FINANCE_QUERY: (),
    SemanticType.TRANSFER: ("amount",),
    SemanticType.PETTY_CASH: ("amount", "recipient_name"),
    SemanticType.REVERSAL: (),
    SemanticType.ACCOUNT_ADMIN: ("action",),
    SemanticType.UNKNOWN: (),
}


def _render_vision_value(value: object) -> str:
    """Render one vision field for the text extraction call that follows.

    Scalars pass through as plain text, exactly as before -- a receipt's
    ``amount: 250`` must keep reading like prose, since that is what the
    extraction prompt was tuned against.

    Lists and dicts are JSON-encoded instead of being str()'d. This matters
    for attendance sheets specifically: a roster arrives as a ``workers``
    array of 15 rows, and Python's repr renders it with single quotes
    (``[{'name': 'Ravi'}]``), which is not JSON and which the extraction
    model then has to re-parse by eye. Nested structure is the one thing an
    attendance sheet cannot afford to lose in this hand-off -- lose it and 15
    named workers collapse into an unparseable blob, which reads exactly like
    the model having failed to read the handwriting.
    """
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


class UnderstandingPipeline:
    def __init__(
        self,
        *,
        speech: SpeechUnderstandingProvider,
        vision: VisionUnderstandingProvider,
        extraction: StructuredExtractionProvider,
        object_storage: ObjectStoragePort,
        confidence_policy: ConfidencePolicy | None = None,
    ) -> None:
        self._speech = speech
        self._vision = vision
        self._extraction = extraction
        self._storage = object_storage
        self._confidence = confidence_policy or ConfidencePolicy()

    async def understand(
        self,
        message: NormalizedMessage,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
    ) -> UnderstandingResult:
        """``semantic_hint`` is an optional nudge from a recent category-menu
        tap (see interactions/category_hint.py) -- it only reaches the
        extraction call, never the deterministic greeting/whoami shortcuts,
        and the provider may still override it if the text clearly disagrees.

        ``expense_categories`` is the caller org's active expense_categories
        names (fetched by the caller — this module must not resolve context
        itself, see the module docstring), threaded through to extraction so
        it can pick a real category instead of inventing free text."""
        result = UnderstandingResult(
            source_message_id=message.message_id,
            correlation_id=message.correlation_id,
            input_modality=message.modality,
            original_content_reference=message.media.object_key if message.media else None,
        )
        try:
            if message.modality in (InputModality.TEXT, InputModality.INTERACTIVE):
                await self._handle_text(
                    message, result, semantic_hint=semantic_hint, expense_categories=expense_categories
                )
            elif message.modality == InputModality.VOICE:
                await self._handle_voice(
                    message, result, semantic_hint=semantic_hint, expense_categories=expense_categories
                )
            elif message.modality in (InputModality.IMAGE, InputModality.DOCUMENT):
                await self._handle_image(
                    message, result, semantic_hint=semantic_hint, expense_categories=expense_categories
                )
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

    async def _handle_text(
        self,
        message: NormalizedMessage,
        result: UnderstandingResult,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
    ) -> None:
        text = (message.text or "").strip()
        if not text:
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.warnings.append("empty text")
            return

        result.transcript = text

        # Deterministic greeting/menu check, before any provider call. In
        # production a text greeting is normally already intercepted by
        # interactions/handler.py's pre-pipeline fast path and never reaches
        # here at all -- this is defense-in-depth so the pipeline is
        # correct in isolation too (direct calls, tests, future callers),
        # not the primary saving. See mesiri_ai.greeting_classifier.
        if is_greeting_trigger(text):
            result.normalized_text = text
            self._apply_deterministic_shortcut(result, SemanticType.UNKNOWN)
            return

        # Same reasoning, for "who am i"/"my profile"/etc -- see
        # mesiri_ai.whoami_classifier. Also defense-in-depth here (the
        # primary saving is interactions/handler.py's pre-pipeline check);
        # the reply itself is built later, in inbound_journey.py (which has
        # the ActorIdentity this module must not know about) by reading
        # semantic_type back off this result -- not by re-running this same
        # classifier a second time on raw text, which is what caused a real
        # bug (the second copy checked the wrong field for voice).
        if is_whoami_trigger(text):
            result.normalized_text = text
            self._apply_deterministic_shortcut(result, SemanticType.WHOAMI_QUESTION)
            return

        # No separate translate_to_english() hop: extract() now reads the
        # original-language text directly and returns detected_language
        # itself (see _EXTRACTION_PROMPT), removing a whole sequential
        # provider round trip from every text message -- previously ~1.9s
        # per message, and the source of three separate silent-failure
        # production bugs (see the Gemini/DeepSeek adapters' git history).
        #
        # Known tradeoff: the is_whoami_trigger phrase list is English-only,
        # and used to get a second, post-translation check here for exactly
        # that reason ("എന്റെ റോൾ എന്താണ്?" never matches until translated).
        # That free shortcut for a non-English whoami question is gone --
        # it now costs one extract() call instead of zero, but is still
        # answered correctly: extract()'s own schema includes
        # "whoami_question" as a semantic_type, so _apply_extraction below
        # classifies it the same way this shortcut would have.
        result.normalized_text = text

        extraction = await self._extraction.extract(
            text,
            semantic_hint=semantic_hint,
            expense_categories=expense_categories,
            correlation_id=result.correlation_id,
        )
        result.detected_language = extraction.detected_language
        self._apply_extraction(result, extraction, is_empty=False)

    async def _handle_voice(
        self,
        message: NormalizedMessage,
        result: UnderstandingResult,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
    ) -> None:
        audio = await self._read_media(message)
        speech = await self._speech.transcribe(audio, correlation_id=result.correlation_id)
        result.transcript = speech.transcript
        result.detected_language = speech.detected_language
        result.translated_text = speech.translated_text
        result.normalized_text = speech.translated_text or speech.transcript
        result.provider_executions.append(
            ProviderExecution(
                provider=speech.provider or "sarvam",
                operation="speech_to_text_translate",
                model=speech.model,
                latency_ms=speech.latency_ms,
            )
        )
        if not (result.normalized_text or "").strip():
            result.overall_confidence = ConfidenceLevel.UNUSABLE
            result.warnings.append("empty transcript")
            return

        # Deterministic greeting/menu check, after transcription (unavoidable
        # for voice) but before extraction. This is the real saving for
        # voice: a spoken "hi" skips the extraction call entirely and is
        # never left to an AI provider's judgment about whether it carries
        # business fields. See mesiri_ai.greeting_classifier.
        if is_greeting_trigger(result.normalized_text):
            self._apply_deterministic_shortcut(result, SemanticType.UNKNOWN)
            return

        # This is the real saving for voice whoami questions ("njaan aara"
        # translates to "who am I" in the same Sarvam call that produced
        # normalized_text above) -- extraction is skipped entirely rather
        # than spent on a question with no business fields to extract.
        # WHOAMI_QUESTION (not UNKNOWN) is the signal inbound_journey.py
        # reads to build the identity-summary reply -- see the comment in
        # _handle_text above for why it reads this instead of re-classifying.
        if is_whoami_trigger(result.normalized_text):
            self._apply_deterministic_shortcut(result, SemanticType.WHOAMI_QUESTION)
            return

        extraction = await self._extraction.extract(
            result.normalized_text,
            semantic_hint=semantic_hint,
            expense_categories=expense_categories,
            correlation_id=result.correlation_id,
        )
        if not result.detected_language:
            # Sarvam's transcribe() genuinely does STT+translate in one call
            # and returns a real detected_language; Gemini's transcribe()
            # only ever transcribes (see the Gemini adapter -- its prompt
            # never asks for translation) and always leaves this None. extract()
            # reads the raw transcript directly and identifies the language
            # itself regardless of which STT provider ran, so it's a strictly
            # better source than "no answer at all" -- this is what stops the
            # control panel from showing a false "Translation did not run"
            # warning on every Gemini-routed voice message.
            result.detected_language = extraction.detected_language
        self._apply_extraction(result, extraction, is_empty=False)

    async def _handle_image(
        self,
        message: NormalizedMessage,
        result: UnderstandingResult,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
    ) -> None:
        image = await self._read_media(message)
        mime = message.media.mime_type if message.media else None
        vision = await self._vision.analyze_image(
            image, mime_type=mime, hint=semantic_hint, correlation_id=result.correlation_id
        )
        result.document_classification = vision.document_classification
        result.normalized_text = vision.description
        result.provider_executions.append(
            ProviderExecution(
                provider=vision.provider or "gemini",
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
        # vision.raw_fields is Gemini's own structured read of the document
        # (amount, vendor, ...) -- description is a *short* prose summary
        # that does not reliably restate every field in words (a receipt
        # description like "Restaurant bill for tea and toast" never
        # mentions the total), so extraction must see raw_fields directly
        # rather than only description, or a real numeric field like amount
        # is silently lost between the vision call and the extraction call.
        source = vision.description or ""
        if vision.raw_fields:
            details = "; ".join(
                f"{key}: {_render_vision_value(value)}" for key, value in vision.raw_fields.items()
            )
            source = f"{source} ({details})" if source else details
        extraction = await self._extraction.extract(
            source,
            semantic_hint=semantic_hint,
            expense_categories=expense_categories,
            correlation_id=result.correlation_id,
        )
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

    def _apply_deterministic_shortcut(
        self, result: UnderstandingResult, semantic_type: SemanticType
    ) -> None:
        """A deterministically recognized greeting/menu or who-am-i request
        (see mesiri_ai.greeting_classifier / mesiri_ai.whoami_classifier) --
        no extraction call, no candidate.

        semantic_type distinguishes the two: UNKNOWN for greeting (the same
        classification an empty extraction would already produce, so it
        flows through canonicalization to CanonicalEventType.UNRECOGNIZED ->
        Planner's DIRECT_REPLY exactly as it does today -- this only makes
        the outcome deterministic rather than dependent on an AI provider
        correctly finding no fields). WHOAMI_QUESTION for who-am-i -- this
        result is the single source of truth callers read (e.g.
        inbound_journey.py checks result.semantic_type directly) rather than
        re-running is_whoami_trigger on raw text a second time downstream,
        which is what let a real bug in: two independent copies of "which
        text field do I check" drifted apart for voice.
        HIGH, not UNUSABLE: we are confident about what this is, we just
        chose not to spend a provider call confirming it.
        """
        result.semantic_type = semantic_type
        result.overall_confidence = ConfidenceLevel.HIGH

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
                provider=extraction.provider or getattr(self._extraction, "provider", "unknown"),
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
