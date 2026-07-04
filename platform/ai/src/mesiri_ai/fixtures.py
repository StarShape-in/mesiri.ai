"""Deterministic understanding fixtures (M3).

Canonical, provider-agnostic results used across tests. These are the reference
inputs the pipeline maps into ``UnderstandingResult`` and that the confidence
policy is graded against. No fixture requires a network call.

Covers the required set: Malayalam JCB voice, valid receipt, partially readable
receipt, unreadable image, empty transcript, provider timeout/unavailable,
malformed structured output, low-confidence extraction.
"""

from __future__ import annotations

import asyncio

from mesiri_contracts.common.errors import MesiriError

from .core.errors import malformed_output, map_provider_error, provider_unavailable
from .models import ExtractionResult, SpeechResult, VisionResult

# --- Voice ------------------------------------------------------------------

# Malayalam JCB voice note -> "the JCB ran for 4 hours".
MALAYALAM_JCB_SPEECH = SpeechResult(
    transcript="ജെസിബി നാല് മണിക്കൂർ ഓടി",
    detected_language="ml",
    translated_text="The JCB ran for 4 hours",
    model="fake-saarika-v2",
    latency_ms=120.0,
)

EMPTY_TRANSCRIPT_SPEECH = SpeechResult(
    transcript="",
    detected_language="ml",
    translated_text="",
    model="fake-saarika-v2",
    latency_ms=90.0,
)

# The equipment-usage extraction expected from the Malayalam JCB voice note.
JCB_EQUIPMENT_EXTRACTION = ExtractionResult(
    semantic_type="equipment_usage",
    fields={"equipment_name": "JCB", "duration_hours": 4},
    field_confidences={"equipment_name": 0.97, "duration_hours": 0.95},
    model="fake-gemini",
    latency_ms=200.0,
)

# --- Image ------------------------------------------------------------------

VALID_RECEIPT_VISION = VisionResult(
    document_classification="receipt",
    description="Hardware store receipt, total 1500 INR",
    raw_fields={"amount": 1500, "currency": "INR", "vendor": "ABC Hardware"},
    model="fake-gemini",
    latency_ms=350.0,
)

VALID_RECEIPT_EXTRACTION = ExtractionResult(
    semantic_type="expense",
    fields={"amount": 1500, "currency": "INR", "vendor": "ABC Hardware"},
    field_confidences={"amount": 0.99, "currency": 0.98, "vendor": 0.9},
    model="fake-gemini",
    latency_ms=210.0,
)

PARTIAL_RECEIPT_VISION = VisionResult(
    document_classification="receipt",
    description="Faded receipt; amount legible, vendor unclear",
    raw_fields={"amount": 1500, "currency": "INR"},
    model="fake-gemini",
    latency_ms=360.0,
)

# Partial receipt -> vendor missing, lower confidence.
PARTIAL_RECEIPT_EXTRACTION = ExtractionResult(
    semantic_type="expense",
    fields={"amount": 1500, "currency": "INR"},
    missing_fields=["vendor"],
    field_confidences={"amount": 0.8, "currency": 0.75},
    warnings=["vendor not legible"],
    model="fake-gemini",
    latency_ms=205.0,
)

UNREADABLE_IMAGE_VISION = VisionResult(
    document_classification="unknown",
    description="Image too blurry to interpret",
    raw_fields={},
    model="fake-gemini",
    latency_ms=300.0,
)

LOW_CONFIDENCE_EXTRACTION = ExtractionResult(
    semantic_type="expense",
    fields={"amount": 1500},
    missing_fields=["currency", "vendor"],
    field_confidences={"amount": 0.35},
    warnings=["low OCR quality"],
    model="fake-gemini",
    latency_ms=205.0,
)


# --- Failure injectors ------------------------------------------------------

def timeout_error() -> MesiriError:
    # Providers raise the already-mapped MesiriError at the port boundary
    # (the adapter maps the raw SDK timeout via the resilience helper).
    return map_provider_error("fake", asyncio.TimeoutError())


def unavailable_error() -> MesiriError:
    return provider_unavailable("fake", "connection refused")


def malformed_error() -> MesiriError:
    return malformed_output("fake", "response was not valid JSON")
