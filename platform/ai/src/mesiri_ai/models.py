"""Provider-agnostic internal models (M3).

Adapters convert provider-specific SDK responses into these Mesiri-owned models
*before* returning them, so no SDK type ever leaks past a provider adapter
(AI Provider Boundary). The understanding pipeline then maps these into the
``UnderstandingResult`` contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

#: Fields that make up ONE intent, pre-Phase-B. Every existing constructor
#: call (adapters, fakes, ~100+ test fixtures across the monorepo) still
#: passes these as top-level ExtractionResult(...) kwargs -- the
#: model_validator(mode="before") on ExtractionResult below translates that
#: legacy shape into intents=[ExtractedIntent(...)] so no caller needs to
#: change for Phase B1/B2/B3 (only the prompt change in B4 and the read-site
#: migration in B5 touch behavior or call sites).
_INTENT_KWARGS = frozenset(
    {
        "semantic_type",
        "fields",
        "unknown_fields",
        "missing_fields",
        "field_confidences",
        "warnings",
    }
)


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


class ExtractedIntent(BaseModel):
    """One distinct request found in a message (Phase B of docs/execution/
    UNIFIED_UNDERSTANDING_PIPELINE.md, ADR-U1). A message may state several
    of these -- "create a project called Bidilaj, then a site called Site
    A, then add Usman as site engineer" is three. Composing, not competing:
    these are NOT rival readings of one request (that axis is
    UnderstandingResult.candidates, a separate model -- see ADR-U3, which
    is explicit that conflating the two would make "did the user ask for
    two things, or might they have meant one of two things?" unanswerable).

    ``fields`` are recognised values; ``unknown_fields`` are provider-
    surfaced keys not modelled by the target schema; ``missing_fields`` are
    required keys the provider could not fill. Values are never fabricated.
    """

    semantic_type: str = "unknown"
    fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Output of a structured-extraction call.

    ``intents`` is the real field, added in Phase B (docs/execution/
    UNIFIED_UNDERSTANDING_PIPELINE.md). Before B4's prompt change, a single
    message still always produces exactly one intent -- the list only
    becomes genuinely plural once the extraction prompt itself is changed
    to ask for every distinct request rather than "the" request.

    ``semantic_type``/``fields``/``unknown_fields``/``missing_fields``/
    ``field_confidences``/``warnings`` below are DERIVED properties reading
    ``intents[0]`` -- kept only so every pre-Phase-B call site (adapters,
    fakes, every existing reader) keeps working unchanged while migration
    proceeds. Removed once nothing reads them (Phase B5). Constructing with
    the OLD top-level kwargs (``ExtractionResult(semantic_type=..., fields=
    ...)``) still works too -- see the model_validator below, which
    translates that legacy constructor shape into ``intents=[...]`` so the
    ~100+ existing call sites across the monorepo need no changes for B1.
    """

    intents: list[ExtractedIntent] = Field(default_factory=list)
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

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_single_intent_kwargs(cls, data: Any) -> Any:
        """Translate the pre-Phase-B constructor shape
        (``ExtractionResult(semantic_type=..., fields=...)``) into
        ``intents=[ExtractedIntent(...)]`` before validation, so every
        existing caller keeps constructing results exactly as it did
        before this field existed. A no-op when ``intents`` is already
        supplied directly (new-style construction) or when data isn't a
        plain dict (e.g. constructing from another model instance)."""
        if isinstance(data, dict) and "intents" not in data:
            intent_data = {k: data.pop(k) for k in list(data.keys()) if k in _INTENT_KWARGS}
            if intent_data:
                data["intents"] = [intent_data]
        return data

    @model_validator(mode="after")
    def _normalize(self) -> ExtractionResult:
        """Empty intents (e.g. ``ExtractionResult()`` with no args at all,
        a real existing pattern in this codebase) normalizes to a single
        default intent -- "no intents" must never be representable, the
        same invariant DecompositionResult's own _normalize enforced for
        its analogous case."""
        if not self.intents:
            self.intents = [ExtractedIntent()]
        return self

    @property
    def semantic_type(self) -> str:
        return self.intents[0].semantic_type

    @property
    def fields(self) -> dict[str, Any]:
        return self.intents[0].fields

    @property
    def unknown_fields(self) -> dict[str, Any]:
        return self.intents[0].unknown_fields

    @property
    def missing_fields(self) -> list[str]:
        return self.intents[0].missing_fields

    @property
    def field_confidences(self) -> dict[str, float]:
        return self.intents[0].field_confidences

    @property
    def warnings(self) -> list[str]:
        return self.intents[0].warnings


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
