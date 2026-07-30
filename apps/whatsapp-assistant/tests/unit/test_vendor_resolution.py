"""_seed_vendor_check -- Phase 4 of ENTITY_RESOLUTION_PLAN.md §5.

The live defect this closes: VendorQueryService only ever did an exact
(case-insensitive) match, and application/vendors/resolution.py creates a
brand-new vendor row for any vendor_text its own exact match misses. So
reporting "Sharma Traders" at an org that already had "Sharma Trading Co"
asked "add it as a new vendor?" and, on Yes, wrote a SECOND row for the same
business -- the §1 Hysam bug with a vendor instead of a person. It compounds
in a way the person case doesn't: every alternate spelling becomes another
row, and the org's spend silently splits across them.

Fakes only: no live DB.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from runtime.entity_resolution.name_matching import NamedCandidate, resolve_name_hint
from runtime.inbound_journey import _seed_vendor_check
from workflows.entities import Ambiguous, Missing, Resolved

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _Actor:
    def __init__(self) -> None:
        self.user_id = USR
        self.organization_id = ORG
        self.role = "SITE_ENGINEER"


class _FakeVendorQuery:
    """Runs the real scorer over a canned vendor list, so these tests cover
    the actual matching rule rather than a hand-stubbed outcome."""

    def __init__(self, *names: str, raises: bool = False) -> None:
        self._candidates = [
            NamedCandidate(entity_id=f"v_{i}", display_name=n) for i, n in enumerate(names)
        ]
        self._raises = raises
        self.calls = 0

    async def resolve(self, *, organization_id: str, vendor_name: str):
        self.calls += 1
        if self._raises:
            raise RuntimeError("db down")
        return resolve_name_hint(vendor_name, self._candidates)


def _event(vendor: str | None = "Sharma Traders") -> CanonicalEventV2:
    fields: dict[str, Any] = {"amount": 2500}
    if vendor is not None:
        fields["vendor"] = vendor
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.EXPENSE_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )


def _decision(
    workflow_key: WorkflowKey = WorkflowKey.EXPENSE_SUBMIT,
) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=workflow_key,
        reason=CanonicalEventType.EXPENSE_REQUESTED,
        organization_id=ORG,
        user_id=USR,
    )


# --- the scorer, on real vendor-shaped names --------------------------------


def test_a_near_miss_business_name_is_ambiguous_not_missing():
    outcome = resolve_name_hint(
        "Sharma Traders", [NamedCandidate(entity_id="v_1", display_name="Sharma Trading Co")]
    )
    assert isinstance(outcome, Ambiguous)
    assert [c.display_name for c in outcome.candidates] == ["Sharma Trading Co"]


def test_an_exact_business_name_resolves():
    outcome = resolve_name_hint(
        "sharma trading co", [NamedCandidate(entity_id="v_1", display_name="Sharma Trading Co")]
    )
    assert isinstance(outcome, Resolved)
    assert outcome.display_name == "Sharma Trading Co"


def test_a_genuinely_new_vendor_is_missing():
    outcome = resolve_name_hint(
        "Indian Oil", [NamedCandidate(entity_id="v_1", display_name="Sharma Trading Co")]
    )
    assert isinstance(outcome, Missing)


# --- the gate ---------------------------------------------------------------


async def test_exact_match_rewrites_to_the_stored_spelling_and_asks_nothing():
    """The duplicate-row fix. The backend re-matches on this exact string, so
    a case/spacing variant has to be normalized to the stored name here or it
    creates a second row."""
    event = _event(vendor="sharma  trading co")
    await _seed_vendor_check(event, _decision(), _FakeVendorQuery("Sharma Trading Co"), _Actor())

    assert event.fields["vendor"] == "Sharma Trading Co"
    assert "vendor_needs_confirmation" not in event.fields
    assert "vendor_candidates" not in event.fields


async def test_a_near_miss_is_offered_as_a_suggestion_rather_than_a_new_vendor():
    event = _event(vendor="Sharma Traders")
    await _seed_vendor_check(event, _decision(), _FakeVendorQuery("Sharma Trading Co"), _Actor())

    assert event.fields["vendor_needs_confirmation"] is True
    assert event.fields["vendor_candidates"] == [
        {"value": "v_0", "label": "Sharma Trading Co"}
    ]
    # Never silently rewritten -- the user picks (ADR-E4 / Ambiguous always asks).
    assert event.fields["vendor"] == "Sharma Traders"


async def test_a_genuinely_new_vendor_keeps_the_plain_add_it_offer():
    event = _event(vendor="Indian Oil")
    await _seed_vendor_check(event, _decision(), _FakeVendorQuery("Sharma Trading Co"), _Actor())

    assert event.fields["vendor_needs_confirmation"] is True
    assert "vendor_candidates" not in event.fields


async def test_an_empty_vendor_book_still_offers_to_add():
    event = _event(vendor="Indian Oil")
    await _seed_vendor_check(event, _decision(), _FakeVendorQuery(), _Actor())

    assert event.fields["vendor_needs_confirmation"] is True


# --- the guards -------------------------------------------------------------


async def test_no_vendor_reported_is_left_completely_alone():
    event = _event(vendor=None)
    query = _FakeVendorQuery("Sharma Trading Co")
    await _seed_vendor_check(event, _decision(), query, _Actor())

    assert query.calls == 0, "an expense with no vendor must not cost a lookup"
    assert "vendor_needs_confirmation" not in event.fields


async def test_a_non_expense_workflow_is_left_alone():
    event = _event()
    query = _FakeVendorQuery("Sharma Trading Co")
    await _seed_vendor_check(event, _decision(WorkflowKey.TRANSFER), query, _Actor())

    assert query.calls == 0


async def test_a_lookup_failure_degrades_to_the_old_behaviour_not_a_lost_expense():
    """Same fail-soft posture as every other gate: never lose the report."""
    event = _event(vendor="Sharma Traders")
    await _seed_vendor_check(
        event, _decision(), _FakeVendorQuery("Sharma Trading Co", raises=True), _Actor()
    )

    assert event.fields["vendor_needs_confirmation"] is True
    assert "vendor_candidates" not in event.fields
    assert event.fields["vendor"] == "Sharma Traders"
