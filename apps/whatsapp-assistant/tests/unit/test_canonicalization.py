"""Canonicalization — unit tests for build_canonical_event (pure, no fakes needed)."""

from __future__ import annotations

import pytest

from canonicalization import build_canonical_event
from mesiri_contracts.assistant.candidates import (
    Candidate,
    ExpenseCandidate,
    FinanceQueryCandidate,
    GeneralQuestionCandidate,
    InventoryQueryCandidate,
    MaterialUpdateCandidate,
    PettyCashCandidate,
    TransferCandidate,
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
    original_content_reference: str | None = None,
) -> UnderstandingResult:
    return UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=semantic_type,
        candidates=candidates or [],
        overall_confidence=overall_confidence,
        original_content_reference=original_content_reference,
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


def test_material_missing_direction_asks_for_it_instead_of_resetting():
    """A message that clearly named a material and quantity but couldn't be
    read as arrived/used (e.g. transcription noise garbled that one word)
    must ask specifically for direction -- not UNRECOGNIZED, which renders
    as a full reset to the category menu (the exact bug this fixes: garbled
    voice reports were sending the user back to "choose a module" instead of
    a targeted clarifying question)."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 20, "unit": "bags"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert event.missing_fields == ["direction"]


def test_material_unrelated_noise_with_no_material_evidence_stays_unrecognized():
    """If there's no sign the message was about material at all (no name, no
    quantity), an unresolved direction must NOT trigger the targeted
    clarification -- that would ask "arrived or used?" about something that
    was never a material report. Falls through to UNRECOGNIZED as before."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[MaterialUpdateCandidate(fields={})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED
    assert event.completeness is IntentCompleteness.NOT_ACTIONABLE


def test_direction_hint_fills_in_when_message_doesnt_resolve_it():
    """A locked direction_hint (from the Material Arrived/Used button tap)
    is used as a fallback default when the message's own words don't give a
    clear received/used -- letting the report proceed as ACTIONABLE instead
    of asking a now-redundant clarifying question."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 20, "unit": "bags"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context(), direction_hint="received")
    assert event.event_type is CanonicalEventType.MATERIAL_RECEIPT_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["direction"] == "received"


def test_direction_hint_never_overrides_an_explicit_spoken_direction():
    """If the message itself clearly says "used", a stale/mismatched
    direction_hint (e.g. the user tapped Arrived but then said "used" in
    their report) must NOT win -- what the user actually said always takes
    priority over a button tap from a moment earlier."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={
                    "material_name": "cement",
                    "quantity": 20,
                    "unit": "bags",
                    "direction": "used",
                }
            )
        ],
    )
    event = build_canonical_event(understanding, _context(), direction_hint="received")
    assert event.event_type is CanonicalEventType.MATERIAL_USAGE_REQUESTED
    assert event.fields["direction"] == "used"


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


def test_finance_query_balance_maps_to_account_balance_query_asked():
    understanding = _understanding(
        semantic_type=SemanticType.FINANCE_QUERY,
        candidates=[FinanceQueryCandidate(fields={"query_kind": "balance", "account_name": "Site Cash"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.ACCOUNT_BALANCE_QUERY_ASKED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["account_name"] == "Site Cash"


def test_finance_query_balance_without_account_name_is_still_actionable():
    """account_name is optional -- absent means "all accounts", not incomplete."""
    understanding = _understanding(
        semantic_type=SemanticType.FINANCE_QUERY,
        candidates=[FinanceQueryCandidate(fields={"query_kind": "balance"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.ACCOUNT_BALANCE_QUERY_ASKED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.missing_fields == []


def test_finance_query_expenses_maps_to_expense_query_asked():
    understanding = _understanding(
        semantic_type=SemanticType.FINANCE_QUERY,
        candidates=[
            FinanceQueryCandidate(
                fields={"query_kind": "expenses", "category_name": "diesel", "date_range": "today"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.EXPENSE_QUERY_ASKED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["category_name"] == "diesel"
    assert event.fields["date_range"] == "today"


def test_finance_query_missing_receipts_flag_is_carried_onto_the_event():
    """Finance Module Slice 6's missing-receipt nudge: the extraction-side
    `missing_receipts` boolean flows through untouched, same generic
    fields-passthrough as any other finance_query field."""
    understanding = _understanding(
        semantic_type=SemanticType.FINANCE_QUERY,
        candidates=[FinanceQueryCandidate(fields={"query_kind": "expenses", "missing_receipts": True})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.EXPENSE_QUERY_ASKED
    assert event.fields["missing_receipts"] is True


def test_finance_query_missing_query_kind_is_unrecognized():
    understanding = _understanding(
        semantic_type=SemanticType.FINANCE_QUERY,
        candidates=[FinanceQueryCandidate(fields={})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED


def test_transfer_maps_to_transfer_requested_actionable():
    understanding = _understanding(
        semantic_type=SemanticType.TRANSFER,
        candidates=[
            TransferCandidate(
                fields={"amount": 50000, "from_account_name": "Company Account", "to_account_name": "Site Cash"}
            )
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.TRANSFER_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["from_account_name"] == "Company Account"
    assert event.fields["to_account_name"] == "Site Cash"


def test_transfer_missing_amount_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.TRANSFER,
        candidates=[TransferCandidate(fields={"from_account_name": "Company Account"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "amount" in event.missing_fields


def test_transfer_without_account_names_is_still_actionable():
    """Account names are optional -- absent means the transfer workflow's
    slot-fill will ask (Finance Module Slice 3)."""
    understanding = _understanding(
        semantic_type=SemanticType.TRANSFER,
        candidates=[TransferCandidate(fields={"amount": 50000})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.TRANSFER_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_petty_cash_issue_maps_to_petty_cash_issue_requested():
    understanding = _understanding(
        semantic_type=SemanticType.PETTY_CASH,
        candidates=[
            PettyCashCandidate(fields={"amount": 20000, "recipient_name": "Alan", "direction": "issue"})
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.PETTY_CASH_ISSUE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["recipient_name"] == "Alan"


def test_petty_cash_return_maps_to_petty_cash_return_requested():
    understanding = _understanding(
        semantic_type=SemanticType.PETTY_CASH,
        candidates=[
            PettyCashCandidate(fields={"amount": 3000, "recipient_name": "Alan", "direction": "return"})
        ],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.PETTY_CASH_RETURN_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_petty_cash_missing_amount_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.PETTY_CASH,
        candidates=[PettyCashCandidate(fields={"recipient_name": "Alan", "direction": "issue"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "amount" in event.missing_fields


def test_petty_cash_missing_recipient_name_needs_clarification():
    understanding = _understanding(
        semantic_type=SemanticType.PETTY_CASH,
        candidates=[PettyCashCandidate(fields={"amount": 20000, "direction": "issue"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "recipient_name" in event.missing_fields


def test_petty_cash_missing_direction_is_unrecognized():
    understanding = _understanding(
        semantic_type=SemanticType.PETTY_CASH,
        candidates=[PettyCashCandidate(fields={"amount": 20000, "recipient_name": "Alan"})],
    )
    event = build_canonical_event(understanding, _context())
    assert event.event_type is CanonicalEventType.UNRECOGNIZED


def test_media_object_key_is_carried_onto_the_event_fields_when_present():
    """Generic across every event type -- not expense-specific -- so a
    confirmed workflow execution can save it as evidence later (see
    RecordExpenseCommand.media_object_key)."""
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 350, "category": "diesel"})],
        original_content_reference="media/wamid.1/abc123",
    )
    event = build_canonical_event(understanding, _context())
    assert event.fields["media_object_key"] == "media/wamid.1/abc123"


def test_media_object_key_is_absent_when_not_an_image():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 350})],
    )
    event = build_canonical_event(understanding, _context())
    assert "media_object_key" not in event.fields


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
