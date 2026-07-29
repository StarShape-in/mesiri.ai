"""_seed_project_detail_query -- "give me all details of this project/site"
seeding branch.

Mirrors test_seed_activity_search.py's shape: fake query services stand in
for the real Postgres-backed ones. What's protected here is pure wiring:
PROJECT_DETAIL_QUERY composes the actor's already-resolved project/site
summaries with the scope-matching results from the four runtime query
services, and role-gates the financial section.
"""

from __future__ import annotations

from backend.ports import ProjectSummary, SiteSummary
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from runtime.inbound_journey import _seed_project_detail_query

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"
OTHER_SITE = "55555555-5555-4555-8555-555555555555"


class _Actor:
    def __init__(self, role: str = "ADMIN"):
        self.organization_id = ORG
        self.user_id = USR
        self.role = role
        self.projects = [
            ProjectSummary(id=PRJ, name="Skyline Towers", location="Kochi", code="SKY-001", status="on_track")
        ]
        self.sites = [
            SiteSummary(id=SITE, name="Block A", project_id=PRJ),
            SiteSummary(id=OTHER_SITE, name="Block B", project_id=PRJ),
        ]


class _FakeActivitySearchService:
    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self._result)


class _FakeLabourQueryService:
    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    async def summarize_attendance(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self._result)


class _FakeExpenseQueryService:
    def __init__(self, expenses: list):
        self._expenses = expenses
        self.calls: list[dict] = []

    async def list_expenses(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._expenses)

    @staticmethod
    def total(expenses):
        from decimal import Decimal

        return sum((e.amount for e in expenses), Decimal("0"))


class _FakeInventoryQueryService:
    def __init__(self, levels: list[dict]):
        self._levels = levels
        self.calls: list[dict] = []

    async def query(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._levels)


class _FakeProjectDetailQueryService:
    def __init__(self, member_count: int = 5):
        self._member_count = member_count
        self.calls: list[dict] = []

    async def count_members(self, **kwargs):
        self.calls.append(kwargs)
        return self._member_count


def _decision(*, project_id: str | None, site_id: str | None) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.PROJECT_DETAIL_QUERY,
        reason=CanonicalEventType.PROJECT_DETAIL_QUERY_ASKED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
    )


def _event(*, project_id: str | None, site_id: str | None) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.PROJECT_DETAIL_QUERY_ASKED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        fields={},
    )


def _empty_activity_results() -> dict:
    return {"activities": [], "activity_count": 3, "open_issues": [], "open_issue_count": 2}


def _empty_labour_results() -> dict:
    return {"headcount": 18, "total_cost": "27000", "named": [], "trades": [], "days": 1}


async def test_project_level_query_composes_project_sites_and_member_count():
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([])
    inventory_service = _FakeInventoryQueryService([{"material_name": "Cement", "unit": "bags"}])
    project_detail_service = _FakeProjectDetailQueryService(member_count=5)
    event = _event(project_id=PRJ, site_id=None)
    decision = _decision(project_id=PRJ, site_id=None)

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(),
        "Asia/Kolkata",
    )

    results = event.fields["project_detail_results"]
    assert results["level"] == "project"
    assert results["project"]["name"] == "Skyline Towers"
    assert results["site"] is None
    assert {s["name"] for s in results["sites"]} == {"Block A", "Block B"}
    assert results["member_count"] == 5
    assert results["activity_count"] == 3
    assert results["open_issue_count"] == 2
    assert results["headcount"] == 18
    assert results["stock_levels"] == [{"material_name": "Cement", "unit": "bags"}]
    assert project_detail_service.calls == [{"project_id": PRJ}]


async def test_site_level_query_has_no_sites_list_or_member_count():
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([])
    inventory_service = _FakeInventoryQueryService([])
    project_detail_service = _FakeProjectDetailQueryService()
    event = _event(project_id=PRJ, site_id=SITE)
    decision = _decision(project_id=PRJ, site_id=SITE)

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(),
        "Asia/Kolkata",
    )

    results = event.fields["project_detail_results"]
    assert results["level"] == "site"
    assert results["site"] == {"id": SITE, "name": "Block A"}
    # Still surfaces the parent project's record-card fields.
    assert results["project"]["name"] == "Skyline Towers"
    assert results["sites"] is None
    assert results["member_count"] is None
    assert project_detail_service.calls == []


async def test_finance_section_present_for_admin_role():
    from dataclasses import dataclass
    from decimal import Decimal

    @dataclass
    class _FakeExpense:
        amount: Decimal

    expense = _FakeExpense(amount=Decimal("1500.00"))
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([expense])
    inventory_service = _FakeInventoryQueryService([])
    project_detail_service = _FakeProjectDetailQueryService()
    event = _event(project_id=PRJ, site_id=None)
    decision = _decision(project_id=PRJ, site_id=None)

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(role="ADMIN"),
        "Asia/Kolkata",
    )

    finance = event.fields["project_detail_results"]["finance"]
    assert finance is not None
    assert finance["total"] == "1500.00"
    assert finance["count"] == 1


async def test_finance_section_absent_for_site_engineer_role():
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([])
    inventory_service = _FakeInventoryQueryService([])
    project_detail_service = _FakeProjectDetailQueryService()
    event = _event(project_id=PRJ, site_id=None)
    decision = _decision(project_id=PRJ, site_id=None)

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(role="SITE_ENGINEER"),
        "Asia/Kolkata",
    )

    assert "finance" not in event.fields["project_detail_results"]
    assert expense_service.calls == []


async def test_unresolved_project_and_site_flags_instead_of_answering_org_wide():
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([])
    inventory_service = _FakeInventoryQueryService([])
    project_detail_service = _FakeProjectDetailQueryService()
    event = _event(project_id=None, site_id=None)
    decision = _decision(project_id=None, site_id=None)

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(),
        "Asia/Kolkata",
    )

    assert event.fields.get("project_detail_unresolved") is True
    assert "project_detail_results" not in event.fields
    assert activity_service.calls == []


async def test_is_a_no_op_for_a_different_workflow():
    activity_service = _FakeActivitySearchService(_empty_activity_results())
    labour_service = _FakeLabourQueryService(_empty_labour_results())
    expense_service = _FakeExpenseQueryService([])
    inventory_service = _FakeInventoryQueryService([])
    project_detail_service = _FakeProjectDetailQueryService()
    event = _event(project_id=PRJ, site_id=None)
    decision = PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.ACTIVITY_QUERY,
        reason=CanonicalEventType.ACTIVITY_QUERY_ASKED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
    )

    await _seed_project_detail_query(
        event,
        decision,
        activity_service,
        labour_service,
        expense_service,
        inventory_service,
        project_detail_service,
        _Actor(),
        "Asia/Kolkata",
    )

    assert activity_service.calls == []
    assert "project_detail_results" not in event.fields


async def test_is_a_safe_no_op_with_actor_none():
    event = _event(project_id=PRJ, site_id=None)
    decision = _decision(project_id=PRJ, site_id=None)

    await _seed_project_detail_query(event, decision, None, None, None, None, None, None, "Asia/Kolkata")

    assert "project_detail_results" not in event.fields
