"""Labour attendance workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (optional
``workflow`` dependency group). Mirrors test_expense_capture_graph.py.

Unit tests cover the matching logic node by node; what this file proves is
the part only the compiled graph can show — that the prefix-matched
conditional edge routes correctly, and specifically that it survives being
re-entered mid-question. Labour is the first workflow whose slot name is not
a fixed constant, so "does the edge still fire on `worker_match:2`?" is a
real question about the graph, not about the node.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from mesiri_contracts.assistant.planner_decision import WorkflowKey  # noqa: E402
from workflows.labour_update.graph import build_labour_attendance_graph  # noqa: E402
from workflows.registry import WorkflowRegistry  # noqa: E402

#: Attendance matching no longer asks anything: match_worker returns only
#: AUTO_MATCHED or NO_MATCH (exact full name AND exact trade, or nothing), so
#: the node's question path is currently unreachable.
#:
#: The node code and these tests are kept rather than deleted because the
#: rule was simplified for *this phase* -- an 80-row register upload produced
#: dozens of unanswerable "is this Ravi the same Ravi?" questions -- and
#: smarter matching is expected to want the question back. Skipped, not
#: commented out, so the gap is visible in every run: a skipped test is not a
#: passing test.
ASKING_IS_DISABLED = pytest.mark.skip(
    reason="attendance matching asks nothing in this phase -- see matching.match_worker"
)

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
RAVI_KUMAR = "55555555-5555-4555-8555-555555555555"
RAVI_S = "66666666-6666-4666-8666-666666666666"


def _base_state(fields: dict, **extra) -> dict:
    state = {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.LABOUR_ATTENDANCE.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": None,
        "collected_fields": fields,
    }
    state.update(extra)
    return state


async def test_headcount_only_report_builds_a_draft_in_one_pass():
    """The fastest possible capture (principle P9): counts only, nobody named,
    no questions, straight to confirmation."""
    graph = build_labour_attendance_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "lines": [
                    {"worker_name": None, "trade": "helper", "headcount": 12, "daily_wage": "600"},
                    {"worker_name": None, "trade": "mason", "headcount": 4, "daily_wage": "900"},
                ],
                "occurred_date": "2026-07-26",
            }
        )
    )

    assert result.get("awaiting_slot") is None
    assert result["draft_action"].action_type is DraftActionType.RECORD_LABOUR_ATTENDANCE
    assert "16 workers" in result["pending_prompt"]
    assert "Confirm this record" in result["pending_prompt"]


@ASKING_IS_DISABLED
async def test_ambiguous_worker_ends_the_pass_at_the_question():
    graph = build_labour_attendance_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "lines": [{"worker_name": "Ravi", "trade": "mason", "headcount": 1}],
                "worker_candidates": [
                    {"worker_id": RAVI_KUMAR, "name": "Ravi Kumar", "trade": "mason"},
                    {"worker_id": RAVI_S, "name": "Ravi S", "trade": "mason"},
                ],
            }
        )
    )

    assert result["awaiting_slot"] == "worker_match:0"
    assert result.get("draft_action") is None
    assert "Ravi Kumar" in result["pending_prompt"]


@ASKING_IS_DISABLED
async def test_answering_the_question_resumes_and_completes_the_draft():
    """Re-invoked exactly as WorkflowRuntime.provide_input does it: the
    persisted collected_fields plus the raw answer plus the stored
    awaiting_slot. Nothing else carries over — the graph has no checkpointer."""
    graph = build_labour_attendance_graph()

    asked = await graph.ainvoke(
        _base_state(
            {
                "lines": [{"worker_name": "Ravi", "trade": "mason", "headcount": 1}],
                "worker_candidates": [
                    {"worker_id": RAVI_KUMAR, "name": "Ravi Kumar", "trade": "mason"},
                    {"worker_id": RAVI_S, "name": "Ravi S", "trade": "mason"},
                ],
            }
        )
    )

    resumed = await graph.ainvoke(
        _base_state(
            {**asked["collected_fields"], "_slot_answer_text": "1"},
            awaiting_slot=asked["awaiting_slot"],
        )
    )

    assert resumed.get("awaiting_slot") is None
    draft = resumed["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_LABOUR_ATTENDANCE
    assert draft.fields["lines"][0]["worker_id"] == RAVI_KUMAR
    assert "Confirm this record" in resumed["pending_prompt"]


@ASKING_IS_DISABLED
async def test_the_conditional_edge_fires_on_a_later_line_index():
    """The reason this edge is prefix-matched rather than an exact slot name:
    the second worker's question is `worker_match:1`, and a graph that only
    recognised a fixed constant would fall through to build_draft with the
    question unanswered."""
    graph = build_labour_attendance_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "lines": [
                    {"worker_name": None, "trade": "helper", "headcount": 12},
                    {"worker_name": "Ravi", "trade": "mason", "headcount": 1},
                ],
                "worker_candidates": [
                    {"worker_id": RAVI_KUMAR, "name": "Ravi Kumar", "trade": "mason"},
                    {"worker_id": RAVI_S, "name": "Ravi S", "trade": "mason"},
                ],
            }
        )
    )

    assert result["awaiting_slot"] == "worker_match:1"
    assert result.get("draft_action") is None


async def test_registry_resolves_the_labour_attendance_key():
    """WorkflowKey.LABOUR_ATTENDANCE existed long before this graph did; until
    now it resolved to None and inbound_journey replied "not supported yet"."""
    registry = WorkflowRegistry()
    graph = registry.get_graph(WorkflowKey.LABOUR_ATTENDANCE)
    assert graph is not None
    assert registry.get_graph(WorkflowKey.LABOUR_ATTENDANCE) is graph
