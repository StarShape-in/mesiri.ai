"""workflows/project_detail_query/nodes.py -- unit tests (pure functions, no
LangGraph needed).

Mirrors workflows/activity_query's own node test shape: hand-build the
collected_fields dict the seed step would have written, assert the
formatted reply.
"""

from __future__ import annotations

from workflows.project_detail_query.nodes import generate_project_detail_reply


def _state(fields: dict) -> dict:
    return {"collected_fields": fields}


def test_unresolved_project_asks_which_one():
    update = generate_project_detail_reply(_state({"project_detail_unresolved": True}))
    assert "which project" in update["pending_prompt"].lower()


def test_missing_results_reports_not_found():
    update = generate_project_detail_reply(_state({}))
    assert "couldn't find" in update["pending_prompt"].lower()


def test_project_level_reply_includes_record_card_sites_and_team():
    results = {
        "level": "project",
        "project": {
            "id": "p1",
            "name": "Skyline Towers",
            "code": "SKY-001",
            "location": "Kochi",
            "status": "on_track",
        },
        "site": None,
        "sites": [{"id": "s1", "name": "Block A"}, {"id": "s2", "name": "Block B"}],
        "member_count": 5,
        "activity_count": 3,
        "open_issue_count": 2,
        "open_issues": [
            {"issue_type": "MATERIAL_SHORTAGE", "severity": "HIGH", "narrative": "Out of cement"}
        ],
        "headcount": 18,
        "labour_cost": "27000",
        "stock_levels": [],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "Skyline Towers" in prompt
    assert "SKY-001" in prompt
    assert "Kochi" in prompt
    assert "Sites (2)" in prompt
    assert "Block A" in prompt
    assert "Team: 5 member" in prompt
    assert "3 activities logged" in prompt
    assert "2 open issue" in prompt
    assert "Material Shortage" in prompt
    assert "18 workers" in prompt


def test_site_level_reply_omits_sites_and_team_but_shows_parent_project():
    results = {
        "level": "site",
        "project": {"id": "p1", "name": "Skyline Towers", "code": None, "location": "Kochi", "status": "on_track"},
        "site": {"id": "s1", "name": "Block A"},
        "sites": None,
        "member_count": None,
        "activity_count": 1,
        "open_issue_count": 0,
        "open_issues": [],
        "headcount": 4,
        "labour_cost": "6000",
        "stock_levels": [],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "Block A" in prompt
    assert "Skyline Towers" in prompt
    assert "Sites (" not in prompt
    assert "Team:" not in prompt


def test_finance_section_shown_when_present():
    results = {
        "level": "project",
        "project": {"id": "p1", "name": "Skyline Towers", "code": None, "location": None, "status": None},
        "site": None,
        "sites": [],
        "member_count": 0,
        "activity_count": 0,
        "open_issue_count": 0,
        "open_issues": [],
        "headcount": 0,
        "labour_cost": "0",
        "finance": {"total": "184500.00", "count": 42, "date_range_label": "This Month"},
        "stock_levels": [],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "184500.00" in prompt
    assert "42 expenses" in prompt


def test_finance_section_omitted_when_absent():
    """The SITE_ENGINEER case -- the seed step withheld the 'finance' key
    entirely, so the reply must never mention spend at all."""
    results = {
        "level": "project",
        "project": {"id": "p1", "name": "Skyline Towers", "code": None, "location": None, "status": None},
        "site": None,
        "sites": [],
        "member_count": 0,
        "activity_count": 0,
        "open_issue_count": 0,
        "open_issues": [],
        "headcount": 0,
        "labour_cost": "0",
        "stock_levels": [],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "Spend" not in prompt


def test_stock_levels_shown_when_present():
    results = {
        "level": "project",
        "project": {"id": "p1", "name": "Skyline Towers", "code": None, "location": None, "status": None},
        "site": None,
        "sites": [],
        "member_count": 0,
        "activity_count": 0,
        "open_issue_count": 0,
        "open_issues": [],
        "headcount": 0,
        "labour_cost": "0",
        "stock_levels": [{"material_name": "Cement", "current_stock": 180, "unit": "bags"}],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "Cement" in prompt
    assert "180" in prompt


def test_no_sites_yet_says_so_instead_of_a_zero_count_line():
    results = {
        "level": "project",
        "project": {"id": "p1", "name": "Skyline Towers", "code": None, "location": None, "status": None},
        "site": None,
        "sites": [],
        "member_count": 0,
        "activity_count": 0,
        "open_issue_count": 0,
        "open_issues": [],
        "headcount": 0,
        "labour_cost": "0",
        "stock_levels": [],
    }
    prompt = generate_project_detail_reply(_state({"project_detail_results": results}))["pending_prompt"]
    assert "No sites yet" in prompt
