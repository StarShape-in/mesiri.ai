"""Builds CanonicalEvent v2 from UnderstandingResult + ResolvedContext v2."""

from __future__ import annotations

import logging

from mesiri_contracts.assistant.candidates import Candidate
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.common.ids import new_id

from .mapping import REQUIRED_FIELDS, resolve_event_type

logger = logging.getLogger(__name__)

_TERMINAL_EVENT_TYPES = frozenset(
    {CanonicalEventType.GENERAL_QUESTION_ASKED, CanonicalEventType.UNRECOGNIZED}
)


def _select_candidate(understanding: UnderstandingResult) -> Candidate | None:
    for candidate in understanding.candidates:
        if candidate.semantic_type == understanding.semantic_type:
            return candidate
    return None


def _missing_required(event_type: CanonicalEventType, fields: dict) -> list[str]:
    required = REQUIRED_FIELDS.get(event_type, ())
    return [name for name in required if not fields.get(name)]


_RECEIVED_SYNONYMS = {
    "arrival",
    "arrived",
    "received",
    "receive",
    "delivery",
    "delivered",
    "deliver",
    "brought",
    "inward",
}
_USED_SYNONYMS = {
    "used",
    "use",
    "usage",
    "consumed",
    "consume",
    "applied",
    "utilized",
    "utilised",
    "outward",
}

# "bag"/"bags"/"sack" reported for the same material must store one
# consistent unit -- otherwise inventory queries (runtime/inventory_query.py
# merges these the same way for already-stored data, but new writes should
# stop adding to the drift) split one material into several stock lines.
_UNIT_ALIASES: dict[str, str] = {
    "bag": "bags",
    "sack": "bags",
    "sacks": "bags",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ton": "tons",
    "tonne": "tons",
    "tonnes": "tons",
    "litre": "litres",
    "liter": "litres",
    "liters": "litres",
    "piece": "pieces",
    "pc": "pieces",
    "pcs": "pieces",
    "roll": "rolls",
    "box": "boxes",
}


def _normalize_material_fields(fields: dict) -> dict:
    """Map common provider aliases onto canonical material field names.

    Every alias key consumed here is popped from the result, not just copied --
    otherwise both the raw alias (``material``, ``event``) and the canonical
    name (``material_name``, ``direction``) end up in the same dict and both
    show up, duplicated, in the confirmation text the user sees."""
    out = dict(fields)
    material_alias = out.pop("material", None)
    if not out.get("material_name") and material_alias:
        out["material_name"] = material_alias

    direction = str(out.get("direction", "")).strip().lower()
    # The provider may have put a synonym directly in `direction`, or used a
    # different key entirely (`event`/`action`/`status`) instead of the exact
    # "received"/"used" the extraction prompt asks for -- check all of them
    # for known vocabulary before giving up as unrecognized. Popped either
    # way: an alias key that didn't resolve to a known direction is noise,
    # not a field the confirmation prompt should ever display.
    event_alias = out.pop("event", None)
    action_alias = out.pop("action", None)
    status_alias = out.pop("status", None)
    if direction not in ("received", "used"):
        candidates = (
            direction,
            str(event_alias or "").strip().lower(),
            str(action_alias or "").strip().lower(),
            str(status_alias or "").strip().lower(),
        )
        for value in candidates:
            if value in _RECEIVED_SYNONYMS:
                out["direction"] = "received"
                break
            if value in _USED_SYNONYMS:
                out["direction"] = "used"
                break

    unit = out.get("unit")
    if unit:
        out["unit"] = _UNIT_ALIASES.get(str(unit).strip().lower(), str(unit).strip())

    return out


def build_canonical_event(
    understanding: UnderstandingResult, context: ResolvedContextV2
) -> CanonicalEventV2:
    """Normalize AI output + resolved context into a CanonicalEvent v2."""
    candidate = _select_candidate(understanding)
    fields: dict = {}
    warnings: list[str] = []
    if candidate is not None:
        fields = {**candidate.fields, **candidate.unknown_fields}
        warnings = list(candidate.warnings)

    if understanding.semantic_type is SemanticType.MATERIAL_UPDATE:
        fields = _normalize_material_fields(fields)

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

    return CanonicalEventV2(
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


def log_canonical_event(event: CanonicalEventV2) -> None:
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
