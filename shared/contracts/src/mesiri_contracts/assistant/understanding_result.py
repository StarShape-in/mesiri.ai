"""UnderstandingResult.v1 — the M3 output contract.

Produced by the Understanding Pipeline from a ``NormalizedMessage``. Captures the
transcript/translation, document classification, structured extraction
candidates, confidence, and provider telemetry — but never business truth,
context resolution, or workflow selection (those are downstream).

Ownership: Ilan.  Required reviewer: Alan.  Version: v1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .candidates import Candidate
from .confidence import ConfidenceLevel
from .enums import InputModality, SemanticType

CONTRACT_VERSION = "v1"


class ProviderExecution(BaseModel):
    """One provider invocation's telemetry (no secrets, no raw payloads)."""

    provider: str
    operation: str
    model: str | None = None
    latency_ms: float | None = None
    succeeded: bool = True
    error_code: str | None = None


class UnderstandingResult(BaseModel):
    version: str = CONTRACT_VERSION

    # Provenance / linkage back to the inbound message.
    source_message_id: str
    correlation_id: str
    input_modality: InputModality

    # Original media pointer (object-storage key), never inline bytes.
    original_content_reference: str | None = None

    # Speech / language.
    transcript: str | None = None
    detected_language: str | None = None
    translated_text: str | None = None
    normalized_text: str | None = None

    # Vision / classification.
    document_classification: str | None = None

    # Semantic understanding.
    semantic_type: SemanticType = SemanticType.UNKNOWN
    candidates: list[Candidate] = Field(default_factory=list)

    # Aggregate quality signals.
    overall_confidence: ConfidenceLevel = ConfidenceLevel.UNUSABLE
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Telemetry.
    provider_executions: list[ProviderExecution] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
