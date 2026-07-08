"""Builds a CanonicalEvent from an UnderstandingResult + ResolvedContext.

Pure mapping function — no I/O, no ports, no AI SDKs, no persistence. Mirrors
how `mesiri_ai.confidence.ConfidencePolicy` is a deterministic function over its
inputs. This is the seam between Context (M4) and Planner (M5): Planner reads
only the CanonicalEvent this module produces, never UnderstandingResult or
ResolvedContext directly.
"""

from __future__ import annotations

import logging

from mesiri_contracts.assistant.candidates import Candidate
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEvent,
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.ids import new_id

from .mapping import REQUIRED_FIELDS, resolve_event_type

logger = logging.getLogger(__name__)

_TERMINAL_EVENT_TYPES = frozenset(
    {CanonicalEventType.GENERAL_QUESTION_ASKED, CanonicalEventType.UNRECOGNIZED}
)


def _select_candidate(understanding: UnderstandingResult) -> Candidate | None:
    """The candidate matching the pipeline's own semantic_type, if any."""
    for candidate in understanding.candidates:
        if candidate.semantic_type == understanding.semantic_type:
            return candidate
    return None


def _missing_required(event_type: CanonicalEventType, fields: dict) -> list[str]:
    required = REQUIRED_FIELDS.get(event_type, ())
    return [name for name in required if not fields.get(name)]


def build_canonical_event(
    understanding: UnderstandingResult, context: ResolvedContext
) -> CanonicalEvent:
    """Normalize AI output + resolved context into a CanonicalEvent.

    Never carries the raw AI confidence score forward — ``completeness`` is a
    business-level judgement about which required fields are present.
    """
    candidate = _select_candidate(understanding)
    fields: dict = {}
    warnings: list[str] = []
    if candidate is not None:
        fields = {**candidate.fields, **candidate.unknown_fields}
        warnings = list(candidate.warnings)

    event_type = resolve_event_type(understanding.semantic_type, fields)

    if event_type in _TERMINAL_EVENT_TYPES:
        completeness = IntentCompleteness.NOT_ACTIONABLE
        missing_fields: list[str] = []
    elif understanding.overall_confidence == ConfidenceLevel.UNUSABLE:
        completeness = IntentCompleteness.NOT_ACTIONABLE
        missing_fields = _missing_required(event_type, fields)
    else:
        missing_fields = _missing_required(event_type, fields)
        if missing_fields:
            completeness = IntentCompleteness.NEEDS_CLARIFICATION
            event_type = CanonicalEventType.CLARIFICATION_REQUIRED
        else:
            completeness = IntentCompleteness.ACTIONABLE

    return CanonicalEvent(
        event_id=new_id("evt"),
        correlation_id=understanding.correlation_id,
        source_message_id=understanding.source_message_id,
        conversation_id=context.conversation_id,
        event_type=event_type,
        completeness=completeness,
        organization_id=context.organization_id,
        user_id=context.user_id,
        project_id=context.project_id,
        site_id=context.site_id,
        permissions=context.permissions,
        fields=fields,
        missing_fields=missing_fields,
        warnings=warnings,
    )


def log_canonical_event(event: CanonicalEvent) -> None:
    """Log the CanonicalEvent for development visibility (not user-facing)."""
    logger.info(
        "CanonicalEvent correlation_id=%s event_type=%s completeness=%s "
        "organization=%s user=%s project=%s site=%s",
        event.correlation_id,
        event.event_type.value,
        event.completeness.value,
        event.organization_id,
        event.user_id,
        event.project_id or "unknown",
        event.site_id or "unknown",
    )
    if event.missing_fields:
        logger.info("CanonicalEvent missing_fields=%s", event.missing_fields)
    if event.warnings:
        logger.info("CanonicalEvent warnings=%s", event.warnings)
