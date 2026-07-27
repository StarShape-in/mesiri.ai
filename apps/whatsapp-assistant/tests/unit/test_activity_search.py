"""Activity search (#17 Search / Ask Mesiri) -- "what did I log today?"

Protects two things: the reply must echo back what was actually logged
(work type, narrative, status) so a supervisor recognises their own entries,
and open issues are reported as a distinct section rather than folded into
the activity count -- "what happened" and "what's blocking us" are two
different questions.
"""

from __future__ import annotations

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.activity_query.nodes import generate_activity_search_reply


def _state(results: dict, **fields) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.ACTIVITY_QUERY.value,
        "correlation_id": "cor_1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "user_id": "22222222-2222-4222-8222-222222222222",
        "collected_fields": {"activity_search_results": results, **fields},
    }


def _reply(results: dict, **fields) -> str:
    return generate_activity_search_reply(_state(results, **fields))["pending_prompt"]


def test_nothing_logged_says_so_plainly():
    reply = _reply(
        {
            "activities": [],
            "activity_count": 0,
            "open_issues": [],
            "open_issue_count": 0,
            "date_range_label": "today",
        }
    )
    assert "nothing logged" in reply.lower()
    assert "today" in reply.lower()


def test_activities_are_echoed_with_work_type_and_narrative():
    reply = _reply(
        {
            "activities": [
                {"work_type": "plastering", "narrative": "180 sqm done", "status": "IN_PROGRESS"},
            ],
            "activity_count": 1,
            "open_issues": [],
            "open_issue_count": 0,
            "date_range_label": "today",
        }
    )
    assert "Plastering" in reply
    assert "180 sqm done" in reply
    assert "In Progress" in reply


def test_open_issues_are_a_separate_section_from_activities():
    reply = _reply(
        {
            "activities": [
                {"work_type": "concreting", "narrative": "slab poured", "status": "COMPLETED"},
            ],
            "activity_count": 1,
            "open_issues": [
                {"issue_type": "MATERIAL_SHORTAGE", "severity": "HIGH", "narrative": "cement short"},
            ],
            "open_issue_count": 1,
            "date_range_label": "today",
        }
    )
    assert "1 entry" in reply
    assert "1 open issue" in reply
    assert "Material Shortage" in reply
    assert "cement short" in reply


def test_issues_alone_with_no_activities_still_reports_them():
    reply = _reply(
        {
            "activities": [],
            "activity_count": 0,
            "open_issues": [{"issue_type": "WEATHER", "severity": "LOW", "narrative": "rain"}],
            "open_issue_count": 1,
            "date_range_label": "this week",
        }
    )
    assert "No activity logged" in reply
    assert "1 open issue" in reply


def test_work_type_filter_is_reflected_in_the_header():
    reply = _reply(
        {
            "activities": [{"work_type": "plastering", "narrative": None, "status": None}],
            "activity_count": 1,
            "open_issues": [],
            "open_issue_count": 0,
            "date_range_label": "today",
        },
        work_type="plastering",
    )
    assert "Plastering" in reply.splitlines()[0]


def test_more_than_max_shown_entries_reports_a_remainder():
    activities = [
        {"work_type": f"work_{i}", "narrative": None, "status": None} for i in range(10)
    ]
    reply = _reply(
        {
            "activities": activities,
            "activity_count": 12,
            "open_issues": [],
            "open_issue_count": 0,
            "date_range_label": "this month",
        }
    )
    assert "more" in reply.lower()
