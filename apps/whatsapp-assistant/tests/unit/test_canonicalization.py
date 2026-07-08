"""Canonicalization — unit tests for build_canonical_event (pure, no fakes needed).

Table-driven over (UnderstandingResult, ResolvedContext) -> expected
(event_type, completeness). No I/O, no ports — this module is a pure mapping
function, same shape of test as mesiri_ai.confidence.ConfidencePolicy.
"""

from __future__ import annotations

import pytest

from canonicalization import build_canonical_event
from mesiri_contracts.assistant.candidates import (
    Candidate,
    EquipmentUsageCandidate,
    ExpenseCandidate,
    GeneralQuestionCandidate,
    LabourUpdateCandidate,
    MaterialUpdateCandidate,
)
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.assistant.understanding_result import UnderstandingResult


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


def _context() -> ResolvedContext:
    return ResolvedContext(
        correlation_id="cor_1",
        source_message_id="msg_1",
        organization_id="org_1",
        user_id="usr_1",
        project_id="prj_1",
        site_id="site_1",
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )


def test_material_received_maps_to_receipt_requested_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 20, "unit": "bags", "direction": "received"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.MATERIAL_RECEIPT_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.missing_fields == []


def test_material_used_maps_to_usage_requested_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "sand", "quantity": 5, "unit": "tons", "direction": "used"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.MATERIAL_USAGE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_material_missing_quantity_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(fields={"material_name": "cement", "direction": "received"})
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "quantity" in event.missing_fields
    assert "unit" in event.missing_fields


def test_material_missing_direction_is_unrecognized():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[MaterialUpdateCandidate(fields={"material_name": "cement", "quantity": 20})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE


def test_expense_with_amount_is_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500, "vendor": "hardware store"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.EXPENSE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["amount"] == 500


def test_expense_missing_amount_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"vendor": "hardware store"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert event.missing_fields == ["amount"]


def test_equipment_usage_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.EQUIPMENT_USAGE,
        candidates=[
            EquipmentUsageCandidate(fields={"equipment_name": "JCB", "duration_hours": 4})
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.EQUIPMENT_USAGE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_labour_attendance_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.LABOUR_UPDATE,
        candidates=[LabourUpdateCandidate(fields={"headcount": 12})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_general_question_is_not_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.GENERAL_QUESTION,
        candidates=[GeneralQuestionCandidate(fields={"question": "when is the next delivery?"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.GENERAL_QUESTION_ASKED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE
    assert event.missing_fields == []


def test_unknown_semantic_type_is_unrecognized():
    understanding = _understanding(semantic_type=SemanticType.UNKNOWN, candidates=[])
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE


def test_unusable_confidence_forces_not_actionable_without_storing_confidence():
    """UNUSABLE understanding gates completeness, but the raw confidence value
    itself must never appear on the CanonicalEvent (layer-ownership boundary)."""
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500})],
        overall_confidence=ConfidenceLevel.UNUSABLE,
    )
    event = build_canonical_event(understanding, _context())
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE
    assert not hasattr(event, "confidence_level")
    assert not hasattr(event, "overall_confidence")


def test_no_candidates_at_all_yields_missing_required_fields():
    understanding = _understanding(semantic_type=SemanticType.EXPENSE, candidates=[])
    event = build_canonical_event(understanding, _context())
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert event.missing_fields == ["amount"]


def test_context_fields_are_denormalized_onto_the_event():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500})],
    )
    ctx = ResolvedContext(
        correlation_id="cor_1",
        source_message_id="msg_1",
        organization_id="org_9",
        user_id="usr_9",
        project_id="prj_9",
        site_id="site_9",
        permissions=["expense.record"],
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )
    event = build_canonical_event(understanding, ctx)
    assert event.organization_id == "org_9"
    assert event.user_id == "usr_9"
    assert event.project_id == "prj_9"
    assert event.site_id == "site_9"
    assert event.permissions == ["expense.record"]


def test_correlation_and_source_message_id_propagate_unchanged():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.correlation_id == "cor_1"
    assert event.source_message_id == "msg_1"


@pytest.mark.parametrize("semantic_type", list(SemanticType))
def test_every_semantic_type_produces_a_valid_event_type(semantic_type: SemanticType) -> None:
    understanding = _understanding(semantic_type=semantic_type, candidates=[])
    event = build_canonical_event(understanding, _context())
    assert isinstance(event.event_type, CanonicalEventType)
