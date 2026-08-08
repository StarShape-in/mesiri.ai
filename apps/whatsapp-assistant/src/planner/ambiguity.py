"""Low-confidence routing (#7) -- decide what to do about a shaky extraction.

Pure, deterministic, no I/O -- same shape as planner.py and confidence.py.
This module is deliberately NOT part of canonicalization: per architecture,
CanonicalEvent must never carry AI-provider or confidence-score knowledge
(canonicalization/builder.py's module docstring). Confidence is instead
consumed here, directly off UnderstandingResult, and the result is a
presentation decision (what to add to the confirmation prompt, or whether to
escalate) -- never folded into the business event itself.

Distinct from the existing "required field missing" gate
(canonicalization/mapping.py's REQUIRED_FIELDS -> IntentCompleteness). That
gate catches a field the provider left EMPTY. This module catches the
opposite and harder case: a field the provider FILLED IN, but wasn't sure
about -- the "confidently wrong" problem from the workflow brief. OCR misreads
"40" as "140"; a mumbled voice note extracts "cement" when it might have been
"sand". Both produce a complete-looking CanonicalEvent that sails straight
through the required-field gate with no question asked.

Principle P10 (docs/execution/DAILY_REPORTING_PLAN.md: never block capture on
a classification the AI didn't confidently make) governs the whole design:
this module NEVER blocks or holds a report. It only decides whether the
eventual confirmation prompt should carry an extra line of caution on ONE
field -- the cheapest possible moment to catch a wrong guess, since the user
is about to read that prompt and tap YES/NO regardless (see
workflows/site_update/nodes.py's "(assumed today)" date caveat for the same
pattern already in production, just for a different signal).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mesiri_contracts.assistant.candidates import Candidate, FieldConfidence
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult

# A field is worth interrupting a confirmation for only if it is a NUMBER a
# wrong guess on which is expensive to unwind (a quantity, an amount, a
# duration) -- never a narrative/description field, where "not fully sure"
# is simply how free text always is and asking about it would be noise on
# every single message. This is the P10 boundary made concrete: the fields
# NOT listed here can be as uncertain as the provider likes without ever
# triggering a caveat.
CRITICAL_FIELDS_BY_TYPE: dict[SemanticType, tuple[str, ...]] = {
    SemanticType.EXPENSE: ("amount",),
    SemanticType.EQUIPMENT_USAGE: ("duration_hours",),
    SemanticType.MATERIAL_UPDATE: ("quantity",),
    SemanticType.LABOUR_UPDATE: ("headcount",),
    SemanticType.TRANSFER: ("amount",),
    SemanticType.PETTY_CASH: ("amount",),
    # Every other SemanticType (GENERAL_SITE_UPDATE, questions, queries,
    # REVERSAL, ACCOUNT_ADMIN) has no field worth a caveat -- either it
    # carries no business-critical number, or (ACCOUNT_ADMIN) its target is
    # always resolved against real records downstream, not trusted verbatim.
}

# Below this per-field confidence, a critical field's value is flagged.
# Deliberately a different, tighter threshold than ConfidencePolicy's
# _MEDIUM_MIN (0.45) -- that threshold governs the OVERALL extraction
# quality bucket (HIGH/MEDIUM/LOW/UNUSABLE); this one governs a single
# number a wrong value on which costs a real correction later, so it is
# allowed to fire even inside an otherwise-HIGH-confidence extraction.
_CRITICAL_FIELD_MIN_CONFIDENCE = 0.6


class AmbiguityAction(str, Enum):
    #: Nothing to flag -- proceed exactly as today.
    PROCEED = "proceed"
    #: One field's value is uncertain enough to caveat on the confirmation
    #: prompt the user is about to see. Never blocks; never asks a SEPARATE
    #: question turn.
    ASK_ONE_QUESTION = "ask_one_question"
    #: The extraction produced nothing usable at all (UNUSABLE overall
    #: confidence). This is the hand-off point to Human Review (#10) --
    #: this module only classifies; it does not itself create an escalation
    #: record (that domain does not exist in this slice; see the module
    #: docstring's note on the boundary this stops at).
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class AmbiguityDecision:
    action: AmbiguityAction
    #: Set only for ASK_ONE_QUESTION -- the single field to caveat.
    field: str | None = None
    #: Set only for ASK_ONE_QUESTION -- 0..1, echoed for logging/telemetry,
    #: never surfaced to the user as a raw number (per the module docstring's
    #: "never carries confidence-score knowledge downstream" boundary --
    #: caveat_text() below renders it as plain language instead).
    field_confidence: float | None = None
    reason: str = ""


_PROCEED = AmbiguityDecision(action=AmbiguityAction.PROCEED)


def _select_candidate(understanding: UnderstandingResult) -> Candidate | None:
    for candidate in understanding.candidates:
        if candidate.semantic_type == understanding.semantic_type:
            return candidate
    return None


def _worst_critical_field(
    candidate: Candidate, critical_fields: tuple[str, ...]
) -> FieldConfidence | None:
    worst: FieldConfidence | None = None
    for fc in candidate.field_confidences:
        if fc.field not in critical_fields:
            continue
        if fc.confidence >= _CRITICAL_FIELD_MIN_CONFIDENCE:
            continue
        if worst is None or fc.confidence < worst.confidence:
            worst = fc
    return worst


def decide_ambiguity(understanding: UnderstandingResult) -> AmbiguityDecision:
    """Classify what (if anything) to do about this extraction's confidence.

    Pure function of ``understanding`` alone -- no context, no canonical
    event, no I/O. Called once per message, independently of canonicalization
    (see module docstring for why the two must stay separate).
    """
    if understanding.overall_confidence is ConfidenceLevel.UNUSABLE:
        return AmbiguityDecision(
            action=AmbiguityAction.ESCALATE,
            reason="overall_confidence=unusable",
        )

    candidate = _select_candidate(understanding)
    if candidate is None:
        return _PROCEED

    critical_fields = CRITICAL_FIELDS_BY_TYPE.get(candidate.semantic_type, ())
    if not critical_fields:
        return _PROCEED

    worst = _worst_critical_field(candidate, critical_fields)
    if worst is None:
        return _PROCEED

    return AmbiguityDecision(
        action=AmbiguityAction.ASK_ONE_QUESTION,
        field=worst.field,
        field_confidence=worst.confidence,
        reason=f"critical_field_low_confidence:{worst.field}",
    )


# Plain-language field names for the caveat line -- never expose the raw
# provider field key (e.g. "duration_hours") to a site worker.
_FIELD_LABEL: dict[str, str] = {
    "amount": "the amount",
    "duration_hours": "the duration",
    "quantity": "the quantity",
    "headcount": "the number of workers",
}


def caveat_text(decision: AmbiguityDecision) -> str | None:
    """One line of plain-language caution to prepend to a confirmation
    prompt, or None when there's nothing to say. Deliberately does not
    render the raw confidence float (see AmbiguityDecision.field_confidence's
    docstring) -- a percentage means nothing to a site worker deciding
    whether to tap YES."""
    if decision.action is not AmbiguityAction.ASK_ONE_QUESTION or decision.field is None:
        return None
    label = _FIELD_LABEL.get(decision.field, decision.field)
    return f"⚠️ Please double-check {label} before confirming — I'm not fully sure I read it right."
