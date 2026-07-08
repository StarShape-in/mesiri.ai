"""Planner (M5) — unit tests for Planner.decide (pure, no fakes needed).

Table-driven over CanonicalEvent -> expected (decision_type, workflow_key).
No I/O, no ports — the Planner is a pure router, same shape of test as
mesiri_ai.confidence.ConfidencePolicy and canonicalization.build_canonical_event.
"""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEvent,
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from planner import Planner
from planner.routing import WORKFLOW_KEY_BY_EVENT


def _event(
    *,
    event_type: CanonicalEventType,
    completeness: IntentCompleteness,
    missing_fields: list[str] | None = None,
) -> CanonicalEvent:
    return CanonicalEvent(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=event_type,
        completeness=completeness,
        organization_id="org_1",
        user_id="usr_1",
        project_id="prj_1",
        site_id="site_1",
        missing_fields=missing_fields or [],
    )


@pytest.mark.parametrize(
    "event_type,expected_key",
    [
        (CanonicalEventType.MATERIAL_RECEIPT_REQUESTED, WorkflowKey.MATERIAL_RECEIPT),
        (CanonicalEventType.MATERIAL_USAGE_REQUESTED, WorkflowKey.MATERIAL_USAGE),
        (CanonicalEventType.EXPENSE_REQUESTED, WorkflowKey.EXPENSE_SUBMIT),
        (CanonicalEventType.EQUIPMENT_USAGE_REQUESTED, WorkflowKey.EQUIPMENT_USAGE),
        (CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED, WorkflowKey.LABOUR_ATTENDANCE),
        (CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED, WorkflowKey.SITE_UPDATE),
    ],
)
def test_actionable_domain_events_start_the_matching_workflow(
    event_type: CanonicalEventType, expected_key: WorkflowKey
) -> None:
    event = _event(event_type=event_type, completeness=IntentCompleteness.ACTIONABLE)
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.START_WORKFLOW
    assert decision.workflow_key is expected_key
    assert decision.reason is event_type


def test_clarification_required_maps_to_clarify_with_missing_fields():
    event = _event(
        event_type=CanonicalEventType.CLARIFICATION_REQUIRED,
        completeness=IntentCompleteness.NEEDS_CLARIFICATION,
        missing_fields=["amount"],
    )
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.CLARIFY
    assert decision.workflow_key is None
    assert decision.missing_fields == ["amount"]


def test_general_question_maps_to_direct_reply():
    event = _event(
        event_type=CanonicalEventType.GENERAL_QUESTION_ASKED,
        completeness=IntentCompleteness.NOT_ACTIONABLE,
    )
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.DIRECT_REPLY
    assert decision.workflow_key is None


def test_unrecognized_maps_to_direct_reply():
    event = _event(
        event_type=CanonicalEventType.UNRECOGNIZED,
        completeness=IntentCompleteness.NOT_ACTIONABLE,
    )
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.DIRECT_REPLY
    assert decision.workflow_key is None


def test_not_actionable_domain_event_maps_to_direct_reply_not_workflow():
    """UNUSABLE-confidence gate: event_type stays a domain *Requested type but
    completeness is NOT_ACTIONABLE — must not start a workflow on bad input."""
    event = _event(
        event_type=CanonicalEventType.EXPENSE_REQUESTED,
        completeness=IntentCompleteness.NOT_ACTIONABLE,
    )
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.DIRECT_REPLY
    assert decision.workflow_key is None


def test_scope_and_correlation_propagate_onto_the_decision():
    event = _event(
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
    )
    decision = Planner().decide(event)
    assert decision.correlation_id == event.correlation_id
    assert decision.source_message_id == event.source_message_id
    assert decision.causation_event_id == event.event_id
    assert decision.organization_id == event.organization_id
    assert decision.user_id == event.user_id
    assert decision.project_id == event.project_id
    assert decision.site_id == event.site_id


def test_routing_table_gap_falls_back_to_direct_reply_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A future actionable CanonicalEventType added without a matching
    WorkflowKey entry must degrade to DIRECT_REPLY, never raise a KeyError."""
    monkeypatch.delitem(WORKFLOW_KEY_BY_EVENT, CanonicalEventType.MATERIAL_RECEIPT_REQUESTED)
    event = _event(
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
    )
    decision = Planner().decide(event)
    assert decision.decision_type is PlannerDecisionType.DIRECT_REPLY
    assert decision.workflow_key is None
