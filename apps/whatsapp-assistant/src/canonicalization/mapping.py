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
    SemanticType.WHOAMI_QUESTION: CanonicalEventType.IDENTITY_LOOKUP_REQUESTED,
    SemanticType.INVENTORY_QUERY: CanonicalEventType.INVENTORY_QUERY_ASKED,
    SemanticType.TRANSFER: CanonicalEventType.TRANSFER_REQUESTED,
    SemanticType.ACCOUNT_ADMIN: CanonicalEventType.ACCOUNT_ADMIN_REQUESTED,
}

# MATERIAL_UPDATE is the one semantic type that splits by the candidate's
# `direction` field (received -> a receipt, used -> usage).
_MATERIAL_DIRECTION_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "received": CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
    "used": CanonicalEventType.MATERIAL_USAGE_REQUESTED,
}

# FINANCE_QUERY is the other semantic type that splits by a candidate field
# -- `query_kind` ("balance" -> account balance, "expenses" -> expense
# list/sum), same pattern as MATERIAL_UPDATE/direction above.
_FINANCE_QUERY_KIND_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "balance": CanonicalEventType.ACCOUNT_BALANCE_QUERY_ASKED,
    "expenses": CanonicalEventType.EXPENSE_QUERY_ASKED,
}

# PETTY_CASH is the third semantic type that splits by a candidate field --
# `direction` ("issue" -> petty cash paid out to someone, "return" -> petty
# cash paid back in), same pattern as MATERIAL_UPDATE/direction above.
_PETTY_CASH_DIRECTION_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "issue": CanonicalEventType.PETTY_CASH_ISSUE_REQUESTED,
    "return": CanonicalEventType.PETTY_CASH_RETURN_REQUESTED,
}

# REVERSAL is the fourth semantic type that splits by a candidate field --
# `target_kind` ("expense" -> void an expense + reverse its payment,
# "transfer" -> reverse a transfer's ledger row directly), same pattern as
# MATERIAL_UPDATE/direction above.
_REVERSAL_TARGET_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "expense": CanonicalEventType.EXPENSE_REVERSAL_REQUESTED,
    "transfer": CanonicalEventType.TRANSFER_REVERSAL_REQUESTED,
}

# Business fields required for an event of this type to be ACTIONABLE.
# Question/Unrecognized events require nothing — they carry no business record.
REQUIRED_FIELDS: dict[CanonicalEventType, tuple[str, ...]] = {
    CanonicalEventType.MATERIAL_RECEIPT_REQUESTED: ("material_name", "quantity", "unit"),
    CanonicalEventType.MATERIAL_USAGE_REQUESTED: ("material_name", "quantity", "unit"),
    CanonicalEventType.EXPENSE_REQUESTED: ("amount",),
    CanonicalEventType.EQUIPMENT_USAGE_REQUESTED: ("equipment_name", "duration_hours"),
    # `lines`, not `headcount`: builder._normalize_labour_fields folds every
    # accepted input shape (workers[], lines[], or a flat headcount/trade)
    # into `lines` before this check runs, so requiring the canonical field
    # covers all three. An attendance naming nobody and counting nobody is
    # genuinely unactionable and asks for clarification.
    CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED: ("lines",),
    CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED: (),
    CanonicalEventType.GENERAL_QUESTION_ASKED: (),
    CanonicalEventType.IDENTITY_LOOKUP_REQUESTED: (),
    CanonicalEventType.INVENTORY_QUERY_ASKED: (),
    CanonicalEventType.ACCOUNT_BALANCE_QUERY_ASKED: (),
    CanonicalEventType.EXPENSE_QUERY_ASKED: (),
    CanonicalEventType.TRANSFER_REQUESTED: ("amount",),
    CanonicalEventType.PETTY_CASH_ISSUE_REQUESTED: ("amount", "recipient_name"),
    CanonicalEventType.PETTY_CASH_RETURN_REQUESTED: ("amount", "recipient_name"),
    # No required fields -- the target is always "the most recent one of
    # this kind", resolved by seeding (runtime/inbound_journey.py), not
    # stated by the user.
    CanonicalEventType.EXPENSE_REVERSAL_REQUESTED: (),
    CanonicalEventType.TRANSFER_REVERSAL_REQUESTED: (),
    # Only `action` -- the action-specific fields (name / target_name+
    # new_name / target_name) can't be expressed here since one
    # CanonicalEventType covers all three actions (see resolve_event_type's
    # docstring -- account_admin deliberately does NOT split by action the
    # way MATERIAL_UPDATE/PETTY_CASH/REVERSAL split by their own field,
    # since all three actions share one workflow with no per-action
    # routing need). workflows/account_admin/nodes.py's build_draft checks
    # action-specific completeness itself and asks for what's missing,
    # mirroring reverse/nodes.py's own "nothing to reverse" completeness
    # check.
    CanonicalEventType.ACCOUNT_ADMIN_REQUESTED: ("action",),
    CanonicalEventType.CLARIFICATION_REQUIRED: (),
    CanonicalEventType.UNRECOGNIZED: (),
}


def resolve_event_type(semantic_type: SemanticType, fields: dict) -> CanonicalEventType:
    """Map a semantic type (+ its candidate fields) to a CanonicalEventType.

    MATERIAL_UPDATE is direction-dependent and FINANCE_QUERY is
    query_kind-dependent; an unrecognized or missing split field falls back
    to UNRECOGNIZED rather than guessing.
    """
    if semantic_type is SemanticType.MATERIAL_UPDATE:
        direction = str(fields.get("direction", "")).strip().lower()
        return _MATERIAL_DIRECTION_EVENT_TYPE.get(direction, CanonicalEventType.UNRECOGNIZED)
    if semantic_type is SemanticType.FINANCE_QUERY:
        query_kind = str(fields.get("query_kind", "")).strip().lower()
        return _FINANCE_QUERY_KIND_EVENT_TYPE.get(query_kind, CanonicalEventType.UNRECOGNIZED)
    if semantic_type is SemanticType.PETTY_CASH:
        direction = str(fields.get("direction", "")).strip().lower()
        return _PETTY_CASH_DIRECTION_EVENT_TYPE.get(direction, CanonicalEventType.UNRECOGNIZED)
    if semantic_type is SemanticType.REVERSAL:
        target_kind = str(fields.get("target_kind", "")).strip().lower()
        return _REVERSAL_TARGET_EVENT_TYPE.get(target_kind, CanonicalEventType.UNRECOGNIZED)
    return _SIMPLE_EVENT_TYPE.get(semantic_type, CanonicalEventType.UNRECOGNIZED)
