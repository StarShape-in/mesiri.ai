"""Provider-agnostic internal models (M3).

Adapters convert provider-specific SDK responses into these Mesiri-owned models
*before* returning them, so no SDK type ever leaks past a provider adapter
(AI Provider Boundary). The understanding pipeline then maps these into the
``UnderstandingResult`` contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class SpeechResult(BaseModel):
    """Output of a speech-understanding call (STT + optional translation).

    Sarvam returns transcript and translated text from a single invocation, so
    translation is not a separate provider operation.
    """

    transcript: str
    detected_language: str | None = None
    translated_text: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None


class TranslationResult(BaseModel):
    """Output of a text-to-text translation call."""

    translated_text: str
    source_language: str | None = None
    detected_language: str | None = None
    target_language: str = "en"
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None


class VisionResult(BaseModel):
    """Output of an image-understanding call."""

    document_classification: str | None = None
    description: str | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None


class ExtractionResult(BaseModel):
    """Output of a structured-extraction call.

    ``fields`` are recognised values; ``unknown_fields`` are provider-surfaced
    keys not modelled by the target schema; ``missing_fields`` are required keys
    the provider could not fill. Values are never fabricated.
    """

    semantic_type: str = "unknown"
    fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    # Populated when extract() is called directly on non-English text (the
    # text path no longer runs a separate translate_to_english() hop -- see
    # understanding/pipeline.py's _handle_text) so nothing downstream needs
    # translation to exist to know what language the sender used.
    detected_language: str | None = None
    # transcript/translated_text are only populated by understand_voice()
    # (see ports/voice_extraction.py) -- the merged transcribe+extract call
    # for voice, which returns everything _handle_voice needs (including
    # what the sender actually said, for logging/display) from one round
    # trip instead of two.
    transcript: str | None = None
    translated_text: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None


class DecompositionResult(BaseModel):
    """Output of a decomposition call -- splitting, not classifying.

    docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9: a message like "create
    a project called Starship and then create a site called Site A, then add
    a new user Hysam" returns ExtractionResult.semantic_type == "unknown",
    because a single semantic_type field cannot represent three intents at
    once. Decomposition is a SEPARATE call from extraction, run only when
    extraction already returned unknown -- it does not classify each part
    (that stays extract()'s job, run once per segment afterward, unchanged),
    it only decides whether the text is actually several distinct requests
    and, if so, where the boundaries are.

    ``segments`` are plain sub-texts in the order the sender said them --
    never reordered here (see planning/ordering.py: dependency order is
    derived later, from what each segment's own extraction produces, not
    imposed at split time). Empty when ``is_multi_intent`` is False; a
    decomposer that isn't confident this is genuinely multiple requests
    should say so via ``is_multi_intent=False`` rather than guess at a split,
    since the fallback (today's single unrecognized-message reply) is safe
    and a wrong split is not.
    """

    is_multi_intent: bool = False
    segments: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None

    @model_validator(mode="after")
    def _normalize(self) -> DecompositionResult:
        """Enforced HERE, once, rather than duplicated per adapter: fewer
        than two non-blank segments is never a split, whatever a provider
        claimed for ``is_multi_intent``. A one-element "split" would turn an
        ordinary single-intent message into a pointless one-step "plan", and
        a provider hallucinating true with an empty list must not silently
        become one either."""
        segments = [s for s in self.segments if s.strip()]
        confirmed = self.is_multi_intent and len(segments) >= 2
        self.is_multi_intent = confirmed
        self.segments = segments if confirmed else []
        return self
