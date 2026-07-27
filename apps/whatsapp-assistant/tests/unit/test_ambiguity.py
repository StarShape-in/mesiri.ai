"""Low-confidence routing (#7) -- truth table for planner/ambiguity.py.

Pure function, no fakes needed -- same shape as test_canonicalization.py.
"""

from __future__ import annotations

from mesiri_contracts.assistant.candidates import (
    Candidate,
    ExpenseCandidate,
    FieldConfidence,
    GeneralSiteUpdateCandidate,
    MaterialUpdateCandidate,
)
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from planner.ambiguity import AmbiguityAction, caveat_text, decide_ambiguity


def _understanding(
    *,
    semantic_type: SemanticType,
    candidates: list[Candidate] | None = None,
    overall_confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> UnderstandingResult:
    return UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=semantic_type,
        candidates=candidates or [],
        overall_confidence=overall_confidence,
    )


def test_unusable_overall_confidence_escalates_regardless_of_candidate():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE, overall_confidence=ConfidenceLevel.UNUSABLE
    )
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.ESCALATE
    assert caveat_text(decision) is None


def test_no_matching_candidate_proceeds():
    understanding = _understanding(semantic_type=SemanticType.MATERIAL_UPDATE, candidates=[])
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED


def test_semantic_type_with_no_critical_fields_always_proceeds():
    # GENERAL_SITE_UPDATE has no entry in CRITICAL_FIELDS_BY_TYPE at all --
    # even a rock-bottom field confidence must never trigger a caveat here,
    # since nothing about a narrative update is a number worth double-
    # checking (P10).
    candidate = GeneralSiteUpdateCandidate(
        fields={"summary": "poured slab"},
        field_confidences=[FieldConfidence(field="summary", confidence=0.05)],
    )
    understanding = _understanding(
        semantic_type=SemanticType.GENERAL_SITE_UPDATE, candidates=[candidate]
    )
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED
    assert caveat_text(decision) is None


def test_low_confidence_narrative_field_never_triggers_a_caveat():
    # material_name is NOT in CRITICAL_FIELDS_BY_TYPE[MATERIAL_UPDATE] --
    # only quantity is. A shaky material name must not interrupt capture.
    candidate = MaterialUpdateCandidate(
        fields={"material_name": "cement", "quantity": 40, "unit": "bags"},
        field_confidences=[
            FieldConfidence(field="material_name", confidence=0.2),
            FieldConfidence(field="quantity", confidence=0.95),
        ],
    )
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE, candidates=[candidate]
    )
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED


def test_low_confidence_critical_field_triggers_ask_one_question():
    candidate = MaterialUpdateCandidate(
        fields={"material_name": "cement", "quantity": 140, "unit": "bags"},
        field_confidences=[
            FieldConfidence(field="material_name", confidence=0.95),
            FieldConfidence(field="quantity", confidence=0.3),
        ],
    )
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE, candidates=[candidate]
    )
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.ASK_ONE_QUESTION
    assert decision.field == "quantity"
    assert decision.field_confidence == 0.3

    text = caveat_text(decision)
    assert text is not None
    assert "quantity" in text
    # The raw confidence number must never leak into user-facing copy.
    assert "0.3" not in text


def test_high_confidence_critical_field_proceeds():
    candidate = ExpenseCandidate(
        fields={"amount": 500},
        field_confidences=[FieldConfidence(field="amount", confidence=0.9)],
    )
    understanding = _understanding(semantic_type=SemanticType.EXPENSE, candidates=[candidate])
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED


def test_confidence_exactly_at_threshold_proceeds_not_asks():
    candidate = ExpenseCandidate(
        fields={"amount": 500},
        field_confidences=[FieldConfidence(field="amount", confidence=0.6)],
    )
    understanding = _understanding(semantic_type=SemanticType.EXPENSE, candidates=[candidate])
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED


def test_multiple_low_confidence_critical_fields_picks_the_single_worst():
    # PETTY_CASH's only critical field is "amount" -- to exercise the
    # "picks the worst of several" branch we need two low-confidence entries
    # for the SAME critical field name, which _worst_critical_field must
    # correctly reduce to one.
    candidate = ExpenseCandidate(
        fields={"amount": 500},
        field_confidences=[
            FieldConfidence(field="amount", confidence=0.4),
            FieldConfidence(field="amount", confidence=0.15),
        ],
    )
    understanding = _understanding(semantic_type=SemanticType.EXPENSE, candidates=[candidate])
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.ASK_ONE_QUESTION
    assert decision.field == "amount"
    assert decision.field_confidence == 0.15


def test_no_field_confidences_at_all_proceeds():
    candidate = ExpenseCandidate(fields={"amount": 500}, field_confidences=[])
    understanding = _understanding(semantic_type=SemanticType.EXPENSE, candidates=[candidate])
    decision = decide_ambiguity(understanding)
    assert decision.action is AmbiguityAction.PROCEED


def test_caveat_text_is_none_for_proceed_and_escalate():
    assert caveat_text(decide_ambiguity(_understanding(semantic_type=SemanticType.EXPENSE))) is None
    escalated = _understanding(
        semantic_type=SemanticType.EXPENSE, overall_confidence=ConfidenceLevel.UNUSABLE
    )
    assert caveat_text(decide_ambiguity(escalated)) is None
