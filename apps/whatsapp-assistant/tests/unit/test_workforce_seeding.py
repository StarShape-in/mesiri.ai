"""Workforce register lookup + the seeding step that feeds match_workers.

Two things are being protected here, and only one of them is ordinary wiring.

The ordinary part: candidates must reach `collected_fields` so the matching
node can use them, because a node may never query a repository itself.

The part worth the file: the stub must never invent a worker. A stub that
returned plausible-looking people would make matching *appear* to work while
attaching real attendance to workers who do not exist — which is precisely
the corruption principle P4 exists to prevent, arriving through the back door
of test scaffolding.
"""

from __future__ import annotations

import json

import pytest

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from runtime.inbound_journey import _seed_worker_candidates
from runtime.workforce_query import STUB_WORKERS_ENV, StubWorkforceQueryService

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"

ROSTER = [
    {"worker_id": "w-ravi", "name": "Ravi Kumar", "trade": "mason", "seen_on_site": True},
    {"worker_id": "w-arun", "name": "Arun", "trade": "painter"},
]


class _Actor:
    organization_id = ORG
    user_id = USR
    role = "site_engineer"


class _RecordingQuery:
    def __init__(self, roster):
        self._roster = roster
        self.calls = 0
        self.scope: dict | None = None

    async def list_worker_candidates(self, *, organization_id, project_id=None, site_id=None):
        self.calls += 1
        self.scope = {
            "organization_id": organization_id,
            "project_id": project_id,
            "site_id": site_id,
        }
        return list(self._roster)


def _decision(key: WorkflowKey = WorkflowKey.LABOUR_ATTENDANCE) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=key,
        reason=CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
    )


def _event(lines) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields={"lines": lines},
    )


NAMED = [{"worker_name": "Ravi", "trade": "mason", "headcount": 1}]
GROUPS = [{"worker_name": None, "trade": "helper", "headcount": 12}]


# --- the stub never invents anyone -----------------------------------------


async def test_the_register_is_empty_by_default(monkeypatch):
    """The honest day-one answer: an organization that has never recorded
    attendance has no register."""
    monkeypatch.delenv(STUB_WORKERS_ENV, raising=False)
    service = StubWorkforceQueryService()
    assert await service.list_worker_candidates(organization_id=ORG) == []


async def test_a_configured_roster_is_returned(monkeypatch):
    monkeypatch.setenv(STUB_WORKERS_ENV, json.dumps(ROSTER))
    service = StubWorkforceQueryService()
    got = await service.list_worker_candidates(organization_id=ORG)
    assert [w["name"] for w in got] == ["Ravi Kumar", "Arun"]
    assert got[0]["seen_on_site"] is True
    assert got[1]["seen_on_site"] is False


@pytest.mark.parametrize("bad", ["not json at all", '{"not": "a list"}', "[1, 2, 3]"])
async def test_a_broken_roster_degrades_to_empty_rather_than_breaking_capture(monkeypatch, bad):
    """A config mistake must not stop a site reporting who turned up."""
    monkeypatch.setenv(STUB_WORKERS_ENV, bad)
    assert await StubWorkforceQueryService().list_worker_candidates(organization_id=ORG) == []


async def test_entries_without_an_id_or_name_are_dropped(monkeypatch):
    """Half a worker is not a worker -- matching needs both to mean anything."""
    monkeypatch.setenv(
        STUB_WORKERS_ENV,
        json.dumps([{"name": "No Id"}, {"worker_id": "w-x"}, {"worker_id": "w-ok", "name": "Ok"}]),
    )
    got = await StubWorkforceQueryService().list_worker_candidates(organization_id=ORG)
    assert [w["worker_id"] for w in got] == ["w-ok"]


async def test_an_explicit_roster_beats_the_environment(monkeypatch):
    monkeypatch.setenv(STUB_WORKERS_ENV, json.dumps(ROSTER))
    service = StubWorkforceQueryService(roster=[])
    assert await service.list_worker_candidates(organization_id=ORG) == []


# --- seeding ---------------------------------------------------------------


async def test_candidates_reach_the_event_for_a_named_report():
    query = _RecordingQuery(ROSTER)
    event = _event(NAMED)
    await _seed_worker_candidates(event, _decision(), query, _Actor())
    assert [w["name"] for w in event.fields["worker_candidates"]] == ["Ravi Kumar", "Arun"]


async def test_the_register_is_scoped_to_the_reported_project_and_site():
    """A worker from another project must never surface as a candidate."""
    query = _RecordingQuery(ROSTER)
    await _seed_worker_candidates(_event(NAMED), _decision(), query, _Actor())
    assert query.scope == {"organization_id": ORG, "project_id": PRJ, "site_id": SITE}


async def test_a_headcount_only_report_never_touches_the_register():
    """Nobody is named, so there is nothing to match -- reading the register
    would be work done to answer a question no one asked. This is the fastest
    and most common way many sites report (P10/P9)."""
    query = _RecordingQuery(ROSTER)
    event = _event(GROUPS)
    await _seed_worker_candidates(event, _decision(), query, _Actor())
    assert query.calls == 0
    assert "worker_candidates" not in event.fields


async def test_a_mixed_report_does_read_the_register():
    query = _RecordingQuery(ROSTER)
    event = _event(NAMED + GROUPS)
    await _seed_worker_candidates(event, _decision(), query, _Actor())
    assert query.calls == 1


async def test_an_empty_register_seeds_nothing_rather_than_an_empty_list():
    """Absent and empty mean the same thing to the node, so don't add a key
    that would show up as plumbing in the draft."""
    query = _RecordingQuery([])
    event = _event(NAMED)
    await _seed_worker_candidates(event, _decision(), query, _Actor())
    assert "worker_candidates" not in event.fields


async def test_other_workflows_are_left_alone():
    query = _RecordingQuery(ROSTER)
    event = _event(NAMED)
    await _seed_worker_candidates(event, _decision(WorkflowKey.EXPENSE_SUBMIT), query, _Actor())
    assert query.calls == 0
    assert "worker_candidates" not in event.fields


async def test_no_actor_or_no_service_is_a_no_op():
    event = _event(NAMED)
    await _seed_worker_candidates(event, _decision(), None, _Actor())
    await _seed_worker_candidates(event, _decision(), _RecordingQuery(ROSTER), None)
    assert "worker_candidates" not in event.fields
