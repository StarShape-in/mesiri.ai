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
    SemanticType.GENERAL_QUESTION: CanonicalEventType.GENERAL_QUESTION_ASKED,
    SemanticType.WHOAMI_QUESTION: CanonicalEventType.IDENTITY_LOOKUP_REQUESTED,
    SemanticType.INVENTORY_QUERY: CanonicalEventType.INVENTORY_QUERY_ASKED,
    SemanticType.LABOUR_QUERY: CanonicalEventType.LABOUR_QUERY_ASKED,
    SemanticType.ACTIVITY_QUERY: CanonicalEventType.ACTIVITY_QUERY_ASKED,
    SemanticType.DPR_REQUEST: CanonicalEventType.DPR_REQUESTED,
    SemanticType.TRANSFER: CanonicalEventType.TRANSFER_REQUESTED,
    SemanticType.ACCOUNT_ADMIN: CanonicalEventType.ACCOUNT_ADMIN_REQUESTED,
    SemanticType.PROJECT_CREATE: CanonicalEventType.PROJECT_CREATE_REQUESTED,
    SemanticType.SITE_CREATE: CanonicalEventType.SITE_CREATE_REQUESTED,
    SemanticType.PROJECT_DETAIL_QUERY: CanonicalEventType.PROJECT_DETAIL_QUERY_ASKED,
    # Always a new site_issues row -- no candidate-field split (issue_type/
    # severity are closed enums the AI picks directly, unlike direction/
    # query_kind/target_kind/update_kind), so this belongs here rather than
    # in one of the _XXX_EVENT_TYPE split tables below.
    SemanticType.SITE_ISSUE: CanonicalEventType.SITE_ISSUE_REPORTED,
    # No candidate-field split any more -- see the retired
    # _SITE_UPDATE_KIND_EVENT_TYPE note below resolve_event_type. update_kind
    # travels as a plain field, read as a hint by the workflow's own
    # resolver, not used to pick a different CanonicalEventType.
    SemanticType.GENERAL_SITE_UPDATE: CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED,
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
# "transfer" -> reverse a transfer's ledger row directly, "activity" ->
# undo a just-created Activity/Progress Update, ADR-D15), same pattern as
# MATERIAL_UPDATE/direction above.
_REVERSAL_TARGET_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "expense": CanonicalEventType.EXPENSE_REVERSAL_REQUESTED,
    "transfer": CanonicalEventType.TRANSFER_REVERSAL_REQUESTED,
    "activity": CanonicalEventType.ACTIVITY_REVERSAL_REQUESTED,
}

# SITE_ISSUE_UPDATE splits by the candidate's `action` field -- same pattern
# as REVERSAL/target_kind above, all three routing to the single
# WorkflowKey.SITE_ISSUE_CLOSE (see planner/routing.py).
_SITE_ISSUE_ACTION_EVENT_TYPE: dict[str, CanonicalEventType] = {
    "acknowledge": CanonicalEventType.SITE_ISSUE_ACKNOWLEDGE_REQUESTED,
    "resolve": CanonicalEventType.SITE_ISSUE_RESOLVE_REQUESTED,
    "wont_fix": CanonicalEventType.SITE_ISSUE_WONT_FIX_REQUESTED,
}

# GENERAL_SITE_UPDATE used to split by `update_kind` here (PROGRESS/PAUSED/
# RESUMED/COMPLETED -> a dedicated ACTIVITY_CONTINUATION_REQUESTED event
# type, same pattern as MATERIAL_UPDATE/direction above). That split was
# retired (docs/execution/ACTIVITY_RESOLUTION_AND_CORRECTION_PLAN.md): it
# decided create-vs-continue from the extracted word alone, before any
# open-activity lookup, which could silently append to the wrong Activity
# (F1) or dead-end when nothing was open (F2). GENERAL_SITE_UPDATE now
# always resolves to GENERAL_SITE_UPDATE_REQUESTED (see _SIMPLE_EVENT_TYPE
# below); `update_kind` still travels as a plain field -- it's read as a
# *hint*, not a router, by workflows/site_update/matching.py's scorer,
# which runs after the open-activity list is known.
#
# CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED is not dead: it still
# has one live producer, canonicalization/builder.py's
# `_build_linked_activity_segment` (the second segment synthesized when a
# material usage names a work_item). planner/routing.py routes it to the
# same merged WorkflowKey.SITE_UPDATE as GENERAL_SITE_UPDATE_REQUESTED, so
# it goes through the identical resolver.

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
    # No required fields -- the target activity is resolved by seeding
    # (runtime/inbound_journey.py's _seed_open_activity), never stated by the
    # user, same reasoning as EXPENSE_REVERSAL_REQUESTED above. A narrative
    # alone ("finished") is a complete, actionable continuation (P10).
    CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED: (),
    CanonicalEventType.GENERAL_QUESTION_ASKED: (),
    CanonicalEventType.IDENTITY_LOOKUP_REQUESTED: (),
    CanonicalEventType.INVENTORY_QUERY_ASKED: (),
    CanonicalEventType.LABOUR_QUERY_ASKED: (),
    CanonicalEventType.ACTIVITY_QUERY_ASKED: (),
    CanonicalEventType.DPR_REQUESTED: (),
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
    CanonicalEventType.ACTIVITY_REVERSAL_REQUESTED: (),
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
    # Only field this project has: a plain create with a required name --
    # unlike account_admin, there's no second action to route around.
    CanonicalEventType.PROJECT_CREATE_REQUESTED: ("name",),
    # Same reasoning as PROJECT_CREATE_REQUESTED -- the project itself is
    # resolved by context, not a candidate field.
    CanonicalEventType.SITE_CREATE_REQUESTED: ("name",),
    # Read-only summary -- no required fields, matches every other *_ASKED
    # query type (ACTIVITY_QUERY_ASKED, DPR_REQUESTED, etc.).
    CanonicalEventType.PROJECT_DETAIL_QUERY_ASKED: (),
    # Mirrors EXPENSE_REQUESTED: ("amount",) -- one required field (the
    # closed-enum issue_type), everything else (severity, narrative, delay)
    # optional.
    CanonicalEventType.SITE_ISSUE_REPORTED: ("issue_type",),
    # No required fields -- the target is always "the most recently
    # reported issue in the right status", resolved by seeding
    # (runtime/inbound_journey.py's _seed_site_issue_close_target), not
    # stated by the user, same reasoning as the REVERSAL entries above.
    CanonicalEventType.SITE_ISSUE_ACKNOWLEDGE_REQUESTED: (),
    CanonicalEventType.SITE_ISSUE_RESOLVE_REQUESTED: (),
    CanonicalEventType.SITE_ISSUE_WONT_FIX_REQUESTED: (),
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
        if not target_kind:
            # #6 Undo: a bare "undo"/"delete that" (mesiri_ai.undo_classifier)
            # names no kind at all -- distinct from a target_kind the
            # extraction provider filled in with something unrecognized,
            # which still falls to UNRECOGNIZED below. EXPENSE_REVERSAL_
            # REQUESTED is only a routing label here (both reversal event
            # types map to WorkflowKey.REVERSE, see planner/routing.py) --
            # the real kind is resolved by runtime/inbound_journey.py's
            # _seed_reversal_target, which compares the latest expense
            # against the latest transfer and writes the winning target_kind
            # back onto fields before the confirmation prompt renders.
            return CanonicalEventType.EXPENSE_REVERSAL_REQUESTED
        return _REVERSAL_TARGET_EVENT_TYPE.get(target_kind, CanonicalEventType.UNRECOGNIZED)
    if semantic_type is SemanticType.SITE_ISSUE_UPDATE:
        action = str(fields.get("action", "")).strip().lower()
        return _SITE_ISSUE_ACTION_EVENT_TYPE.get(action, CanonicalEventType.UNRECOGNIZED)
    return _SIMPLE_EVENT_TYPE.get(semantic_type, CanonicalEventType.UNRECOGNIZED)
