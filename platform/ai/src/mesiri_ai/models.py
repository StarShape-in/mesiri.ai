"""Provider-agnostic internal models (M3).

Adapters convert provider-specific SDK responses into these Mesiri-owned models
*before* returning them, so no SDK type ever leaks past a provider adapter
(AI Provider Boundary). The understanding pipeline then maps these into the
``UnderstandingResult`` contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SpeechResult(BaseModel):
    """Output of a speech-understanding call (STT + optional translation).

    Sarvam returns transcript and translated text from a single invocation, so
    translation is not a separate provider operation.
    """

    transcript: str
    detected_language: str | None = None
    translated_text: str | None = None
    model: str | None = None
    latency_ms: float | None = None


class VisionResult(BaseModel):
    """Output of an image-understanding call."""

    document_classification: str | None = None
    description: str | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)
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
    model: str | None = None
    latency_ms: float | None = None


class TranslationResult(BaseModel):
    """Output of a text-translation call.

    Carries the translated text alongside metadata so callers can decide
    whether to surface the translation or fall back to the original.
    """

    translated_text: str
    source_language: str | None = None
    target_language: str = "en"
    model: str | None = None
    latency_ms: float | None = None
