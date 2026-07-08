"""Static mapping tables from understanding output to canonical business intent.

Pure data — no I/O, no ports, no AI SDKs. `apps/whatsapp-assistant/src/canonicalization`
depends only on `mesiri_contracts.assistant.*` per the assistant's dependency rules.
"""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.enums import SemanticType

# SemanticType -> CanonicalEventType for the semantic types that resolve to a
# single event type regardless of candidate fields.
_SIMPLE_EVENT_TYPE: dict[SemanticType, CanonicalEventType] = {
    SemanticType.EXPENSE: CanonicalEventType.EXPENSE_REQUESTED,
    SemanticType.EQUIPMENT_USAGE: CanonicalEventType.EQUIPMENT_USAGE_REQUESTED,
    SemanticType.LABOUR_UPDATE: CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED,
    SemanticType.GENERAL_SITE_UPDATE: CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED,
    SemanticType.GENERAL_QUESTION: CanonicalEventType.GENERAL_QUESTION_ASKED,
}

# MATERIAL_UPDATE is the one semantic type that splits by the candidate's
# `direction` field (received -> a receipt, used -> usage).
_MATERIAL_DIRECTION_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "received": CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
    "used": CanonicalEventType.MATERIAL_USAGE_REQUESTED,
}

# Business fields required for an event of this type to be ACTIONABLE.
# Question/Unrecognized events require nothing — they carry no business record.
REQUIRED_FIELDS: dict[CanonicalEventType, tuple[str, ...]] = {
    CanonicalEventType.MATERIAL_RECEIPT_REQUESTED: ("material_name", "quantity", "unit"),
    CanonicalEventType.MATERIAL_USAGE_REQUESTED: ("material_name", "quantity", "unit"),
    CanonicalEventType.EXPENSE_REQUESTED: ("amount",),
    CanonicalEventType.EQUIPMENT_USAGE_REQUESTED: ("equipment_name", "duration_hours"),
    CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED: ("headcount",),
    CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED: (),
    CanonicalEventType.GENERAL_QUESTION_ASKED: (),
    CanonicalEventType.CLARIFICATION_REQUIRED: (),
    CanonicalEventType.UNRECOGNIZED: (),
}


def resolve_event_type(semantic_type: SemanticType, fields: dict) -> CanonicalEventType:
    """Map a semantic type (+ its candidate fields) to a CanonicalEventType.

    MATERIAL_UPDATE is direction-dependent; an unrecognized or missing direction
    falls back to UNRECOGNIZED rather than guessing.
    """
    if semantic_type is SemanticType.MATERIAL_UPDATE:
        direction = str(fields.get("direction", "")).strip().lower()
        return _MATERIAL_DIRECTION_EVENT_TYPE.get(direction, CanonicalEventType.UNRECOGNIZED)
    return _SIMPLE_EVENT_TYPE.get(semantic_type, CanonicalEventType.UNRECOGNIZED)
