"""_seed_reversal_target -- the #6 Undo generic-kind resolution branch.

Mirrors test_workforce_seeding.py's shape: a fake ReversalTargetQueryService
stands in for the real Postgres-backed one (which needs a live DB and is
covered by that repository's own SQL, not here). What's protected here is
pure wiring: a bare "undo" (no target_kind) must resolve via
find_latest_of_either_kind and write the winning kind back onto fields so
workflows/reverse/nodes.py renders the right confirmation prompt.
"""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from runtime.inbound_journey import _seed_reversal_target

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


class _Actor:
    organization_id = ORG
    user_id = USR
    role = "site_engineer"


class _FakeReversalQuery:
    def __init__(self, *, either_kind_result=None, transfer=None, expense=None):
        self._either_kind_result = either_kind_result
        self._transfer = transfer
        self._expense = expense
        self.either_kind_calls = 0

    async def find_latest_of_either_kind(self, *, organization_id, project_id, site_id):
        self.either_kind_calls += 1
        return self._either_kind_result

    async def find_latest_transfer(self, *, organization_id):
        return self._transfer

    async def find_latest_expense(self, *, organization_id, project_id, site_id):
        return self._expense


def _decision() -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.REVERSE,
        reason=CanonicalEventType.EXPENSE_REVERSAL_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
    )


def _event(fields: dict) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.EXPENSE_REVERSAL_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields,
    )


async def test_missing_target_kind_calls_find_latest_of_either_kind():
    query = _FakeReversalQuery(
        either_kind_result=(
            "expense",
            {
                "expense_id": "exp-1",
                "amount": "500",
                "description": "diesel",
                "occurred_date": "2026-07-20",
            },
        )
    )
    event = _event({})
    await _seed_reversal_target(event, _decision(), query, _Actor())

    assert query.either_kind_calls == 1
    assert event.fields["target_kind"] == "expense"
    assert event.fields["expense_id"] == "exp-1"
    assert event.fields["reversal_amount"] == "500"


async def test_missing_target_kind_resolving_to_transfer_writes_transfer_fields():
    query = _FakeReversalQuery(
        either_kind_result=(
            "transfer",
            {
                "money_transaction_id": "txn-1",
                "amount": "1000",
                "from_account_name": "Petty Cash",
                "to_account_name": "Site Bank",
            },
        )
    )
    event = _event({})
    await _seed_reversal_target(event, _decision(), query, _Actor())

    assert event.fields["target_kind"] == "transfer"
    assert event.fields["money_transaction_id"] == "txn-1"
    assert event.fields["reversal_from_account_name"] == "Petty Cash"
    assert event.fields["reversal_to_account_name"] == "Site Bank"


async def test_nothing_found_leaves_target_kind_unset_for_the_generic_message():
    query = _FakeReversalQuery(either_kind_result=None)
    event = _event({})
    await _seed_reversal_target(event, _decision(), query, _Actor())

    # Deliberately absent -- workflows/reverse/nodes.py's build_draft falls
    # through to its generic "Nothing found to reverse." message for any
    # unrecognized target_kind (see mapping.py/reverse/nodes.py docstrings).
    assert "target_kind" not in event.fields
    assert "expense_id" not in event.fields
    assert "money_transaction_id" not in event.fields


async def test_explicit_target_kind_skips_the_either_kind_lookup_entirely():
    """An explicit "reverse my last expense" must not pay for (or risk being
    overridden by) the generic either-kind comparison -- existing, narrower
    behavior is untouched by the #6 Undo addition."""
    query = _FakeReversalQuery(
        either_kind_result=("transfer", {"money_transaction_id": "should-not-be-used"}),
        expense={
            "expense_id": "exp-explicit",
            "amount": "250",
            "description": "cement",
            "occurred_date": "2026-07-25",
        },
    )
    event = _event({"target_kind": "expense"})
    await _seed_reversal_target(event, _decision(), query, _Actor())

    assert query.either_kind_calls == 0
    assert event.fields["expense_id"] == "exp-explicit"
    assert "money_transaction_id" not in event.fields
