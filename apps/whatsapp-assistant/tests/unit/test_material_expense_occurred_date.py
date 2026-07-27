"""Material and Expense now date themselves the same way Labour does (STA-166).

Before this, both silently stamped date.today() at confirm time -- a stated
"yesterday" was thrown away, and "today" meant the server's UTC today, not
the site's. canonicalization/occurred_date.py already had its own thorough
test suite (test_occurred_date.py) for the parsing/timezone logic itself;
what's worth pinning here is narrower and specific to this backport: that
MATERIAL_UPDATE and EXPENSE actually get dated now, the same way
test_labour_canonicalization.py already pins for LABOUR_UPDATE.
"""

from __future__ import annotations

from canonicalization import build_canonical_event
from mesiri_contracts.assistant.candidates import ExpenseCandidate, MaterialUpdateCandidate
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


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


def _material_event(fields: dict):
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[MaterialUpdateCandidate(fields=fields)],
        overall_confidence=ConfidenceLevel.HIGH,
    )
    return build_canonical_event(understanding, _context())


def _expense_event(fields: dict):
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields=fields)],
        overall_confidence=ConfidenceLevel.HIGH,
    )
    return build_canonical_event(understanding, _context())


# --- material ---------------------------------------------------------------


def test_a_stated_material_date_is_honoured():
    event = _material_event(
        {"material_name": "Cement", "quantity": 50, "unit": "bags", "direction": "received",
         "occurred_on": "2026-07-20"}
    )
    assert event.fields["occurred_date"] == "2026-07-20"
    assert event.fields["occurred_date_source"] == "stated_by_user"


def test_a_material_report_with_no_stated_date_is_marked_assumed():
    event = _material_event(
        {"material_name": "Cement", "quantity": 50, "unit": "bags", "direction": "received"}
    )
    assert event.fields["occurred_date"]
    assert event.fields["occurred_date_source"] == "inferred_at_confirmation"


def test_the_raw_occurred_on_does_not_survive_into_material_fields():
    """It would render as its own meaningless line otherwise -- same
    alias-popping discipline _normalize_material_fields already follows for
    material/event."""
    event = _material_event(
        {"material_name": "Cement", "quantity": 50, "unit": "bags", "direction": "received",
         "occurred_on": "yesterday"}
    )
    assert "occurred_on" not in event.fields


def test_a_material_clarification_request_still_carries_a_date():
    """The direction-missing early-return path runs after dating, not before
    -- so the field survives into the re-run once direction is answered."""
    event = _material_event({"material_name": "Cement", "quantity": 50})
    assert "occurred_date" in event.fields


# --- expense -----------------------------------------------------------------


def test_a_stated_expense_date_is_honoured():
    event = _expense_event({"amount": 250, "category": "fuel", "occurred_on": "yesterday"})
    assert event.fields["occurred_date_source"] == "stated_by_user"


def test_an_expense_with_no_stated_date_is_marked_assumed():
    event = _expense_event({"amount": 250, "category": "fuel"})
    assert event.fields["occurred_date"]
    assert event.fields["occurred_date_source"] == "inferred_at_confirmation"


def test_the_raw_occurred_on_does_not_survive_into_expense_fields():
    event = _expense_event({"amount": 250, "category": "fuel", "occurred_on": "2026-07-01"})
    assert "occurred_on" not in event.fields
