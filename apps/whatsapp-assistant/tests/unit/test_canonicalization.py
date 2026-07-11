"""Canonicalization — unit tests for build_canonical_event (pure, no fakes needed)."""

from __future__ import annotations

import pytest

from canonicalization import build_canonical_event
from mesiri_contracts.assistant.candidates import (
    Candidate,
    ExpenseCandidate,
    GeneralQuestionCandidate,
    InventoryQueryCandidate,
    MaterialUpdateCandidate,
)
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


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


def _context() -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="org_1",
        context_user_id="usr_1",
        context_project_id="prj_1",
        context_site_id="site_1",
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )


def test_material_provider_aliases_normalize_to_receipt_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={
                    "material": "UltraTech cement",
                    "quantity": 50,
                    "unit": "bags",
                    "supplier": "ABC Suppliers",
                    "event": "arrival",
                }
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.MATERIAL_RECEIPT_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["material_name"] == "UltraTech cement"
    assert event.fields["direction"] == "received"
    # The raw provider aliases must be popped, not just copied alongside the
    # canonical names -- otherwise the confirmation prompt (which lists every
    # field in event.fields) shows "material" and "material_name" as two
    # separate, duplicated lines for the same value.
    assert "material" not in event.fields
    assert "event" not in event.fields
    assert event.fields["direction"] == "received"


def test_material_received_maps_to_receipt_requested_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={
                    "material_name": "cement",
                    "quantity": 20,
                    "unit": "bags",
                    "direction": "received",
                }
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
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 20, "unit": "bags"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE


def test_expense_complete_is_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500, "vendor": "ABC Hardware"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.EXPENSE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_expense_missing_amount_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"vendor": "ABC Hardware"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "amount" in event.missing_fields


def test_inventory_query_with_material_name_is_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.INVENTORY_QUERY,
        candidates=[InventoryQueryCandidate(fields={"material_name": "cement"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["material_name"] == "cement"


def test_inventory_query_without_material_name_is_still_actionable():
    """material_name is optional -- absent means "all materials", not incomplete."""
    understanding = _understanding(
        semantic_type=SemanticType.INVENTORY_QUERY,
        candidates=[InventoryQueryCandidate(fields={})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.missing_fields == []


def test_general_question_is_not_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.GENERAL_QUESTION,
        candidates=[GeneralQuestionCandidate(fields={"question": "What is the project status?"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.GENERAL_QUESTION_ASKED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE


def test_unusable_confidence_forces_not_actionable_without_storing_confidence():
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
    ctx = ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="org_9",
        context_user_id="usr_9",
        context_project_id="prj_9",
        context_site_id="site_9",
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        permissions=["expense.record"],
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )
    event = build_canonical_event(understanding, ctx)
    assert event.organization_id == ORG
    assert event.user_id == USR
    assert event.project_id == PRJ
    assert event.site_id == SITE
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
