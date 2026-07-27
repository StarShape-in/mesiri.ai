"""Labour query — "how many workers today?"

Two things are being protected.

The reply must echo attendance back the way it was reported: named workers by
name, groups as counts (principle P10 carried to the read side). A supervisor
who wrote "Ravi mason, 12 helpers" should recognise the answer at a glance
rather than decode a total.

And the summary arithmetic must not quietly mislead. Headcount over a
multi-day range is worker-days, not people — reporting "14 workers" for a
week when it was 2 people over 7 days would be read as 14 individuals.
"""

from __future__ import annotations

import datetime

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from runtime.labour_query_service import _summarize, resolve_date_range
from workflows.labour_query.nodes import generate_labour_query_reply

MONDAY = datetime.date(2026, 7, 27)


def _state(results: dict, **fields) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.LABOUR_QUERY.value,
        "correlation_id": "cor_1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "user_id": "22222222-2222-4222-8222-222222222222",
        "collected_fields": {"labour_results": results, **fields},
    }


def _reply(results: dict, **fields) -> str:
    return generate_labour_query_reply(_state(results, **fields))["pending_prompt"]


def _row(name=None, trade="helper", headcount=1, wage=None, day=MONDAY):
    return {
        "worker_name": name,
        "trade": trade,
        "headcount": headcount,
        "daily_wage": wage,
        "occurred_date": day,
    }


# --- date ranges -----------------------------------------------------------


def test_the_default_range_is_today_not_this_month():
    """Expense defaults to "this month"; attendance is a daily rhythm and the
    question a supervisor actually asks is "how many workers today"."""
    start, end, label = resolve_date_range(None, today=MONDAY)
    assert (start, end, label) == (MONDAY, MONDAY, "today")


def test_this_week_runs_from_monday():
    start, end, label = resolve_date_range("this_week", today=datetime.date(2026, 7, 29))
    assert start == MONDAY
    assert end == datetime.date(2026, 7, 29)
    assert label == "this week"


def test_this_month_runs_from_the_first():
    start, _, label = resolve_date_range("this_month", today=datetime.date(2026, 7, 29))
    assert start == datetime.date(2026, 7, 1)
    assert label == "this month"


# --- summarising -----------------------------------------------------------


def test_headcount_counts_people_across_named_and_group_lines():
    summary = _summarize([_row("Ravi", "mason"), _row(None, "helper", headcount=12)])
    assert summary["headcount"] == 13


def test_cost_multiplies_the_wage_by_the_headcount():
    """A group line of 12 at ₹600 is ₹7,200, not ₹600."""
    summary = _summarize([_row(None, "helper", headcount=12, wage="600")])
    assert summary["total_cost"] == "7200"


def test_a_line_with_no_wage_contributes_nothing_rather_than_breaking():
    """A wage-less report is a legitimate fast capture (P9), not an error."""
    summary = _summarize([_row("Ravi", "mason"), _row(None, "helper", headcount=4, wage="500")])
    assert summary["total_cost"] == "2000"
    assert summary["headcount"] == 5


def test_a_worker_on_several_days_is_listed_once():
    """"Who worked this week" listing the same name five times is useless."""
    summary = _summarize(
        [
            _row("Ravi", "mason", day=MONDAY),
            _row("Ravi", "mason", day=MONDAY + datetime.timedelta(days=1)),
        ]
    )
    assert summary["named"] == ["Ravi"]
    # But headcount is worker-days -- it is what cost is derived from.
    assert summary["headcount"] == 2
    assert summary["days"] == 2


def test_trades_are_deduplicated_and_keep_report_order():
    summary = _summarize([_row("Ravi", "mason"), _row("Suresh", "mason"), _row(None, "helper", 4)])
    assert summary["trades"] == ["mason", "helper"]


def test_a_junk_headcount_falls_back_to_one_rather_than_breaking_the_answer():
    summary = _summarize([_row("Ravi", "mason", headcount="many")])
    assert summary["headcount"] == 1


# --- the reply -------------------------------------------------------------


def test_the_reply_shows_headcount_cost_and_names():
    prompt = _reply(
        {
            "headcount": 14,
            "total_cost": "9200",
            "named": ["Ravi Kumar", "Arun"],
            "named_total": 2,
            "trades": ["mason", "painter", "helper"],
            "days": 1,
            "date_range_label": "today",
        }
    )
    assert "14 workers" in prompt
    assert "₹9,200" in prompt
    assert "Ravi Kumar, Arun" in prompt
    assert "Mason, Painter, Helper" in prompt


def test_a_multi_day_answer_says_worker_days_not_workers():
    """2 people over 7 days is 14 worker-days. Calling that "14 workers"
    would be read as 14 individuals."""
    prompt = _reply(
        {"headcount": 14, "total_cost": "0", "named": [], "trades": [], "days": 7,
         "date_range_label": "this week"}
    )
    assert "14 worker-days across 7 days" in prompt
    assert "14 workers" not in prompt


def test_nothing_recorded_says_so_plainly():
    prompt = _reply({"headcount": 0, "total_cost": "0", "named": [], "trades": [], "days": 0,
                     "date_range_label": "today"})
    assert "No attendance recorded for today" in prompt


def test_a_trade_filter_is_named_in_the_answer():
    prompt = _reply(
        {"headcount": 4, "total_cost": "0", "named": [], "trades": ["mason"], "days": 1,
         "date_range_label": "today"},
        trade="mason",
    )
    assert "Mason" in prompt
    assert "4 workers" in prompt


def test_cost_is_omitted_when_no_wages_are_known():
    """Showing "Cost: ₹0" would read as free labour rather than unknown."""
    prompt = _reply({"headcount": 6, "total_cost": "0", "named": [], "trades": ["helper"],
                     "days": 1, "date_range_label": "today"})
    assert "Cost" not in prompt


def test_a_single_worker_reads_naturally():
    prompt = _reply({"headcount": 1, "total_cost": "0", "named": ["Ravi"], "named_total": 1,
                     "trades": ["mason"], "days": 1, "date_range_label": "today"})
    assert "1 worker" in prompt
    assert "1 workers" not in prompt


def test_a_long_roster_is_truncated_with_a_count():
    prompt = _reply(
        {
            "headcount": 30,
            "total_cost": "0",
            "named": [f"Worker {i}" for i in range(10)],
            "named_total": 25,
            "trades": [],
            "days": 1,
            "date_range_label": "today",
        }
    )
    assert "and 15 more named" in prompt


def test_the_query_never_produces_a_draft():
    """Informational: it answers and stops. Nothing is saved, nothing is
    confirmed."""
    update = generate_labour_query_reply(_state({"headcount": 3, "total_cost": "0", "named": [],
                                                 "trades": [], "days": 1}))
    assert "draft_action" not in update
    assert update["pending_prompt"]
