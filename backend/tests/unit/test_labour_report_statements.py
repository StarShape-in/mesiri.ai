"""Labour report statements — the arithmetic, pinned.

These cover the half of the report engine that decides what a supervisor
sees: costs, averages, days worked, percentages, and which workers appear at
all. They are deliberately pure — no database — because this is where the
previous implementation went wrong. It computed reports in the browser off
the worker register, priced it at an assumed 800/day and asserted a 10- or
30-day month for everyone on it (docs/plans/labour-reports-audit.md §2.1).

The SQL that produces these rows is pinned separately in
test_labour_report_aggregation.py.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from mesiri.domains.workforce.reports import (
    UNSPECIFIED_CONTRACTOR,
    UNSPECIFIED_TRADE,
    AggregateRow,
    average_daily_wage,
    build_statement,
    contribution_percentage,
    resolve_group_by,
)

GENERATED = datetime.datetime(2026, 7, 29, 9, 0, 0)


def _row(**overrides) -> AggregateRow:
    defaults = dict(
        key="mason",
        label="Mason",
        man_days=10,
        priced_man_days=10,
        total_cost=Decimal("8000.00"),
        days_worked=2,
    )
    defaults.update(overrides)
    return AggregateRow(**defaults)


# --- Labour cost ----------------------------------------------------------

def test_cost_is_carried_through_exactly_never_rounded_into_float():
    """The wage that once broke this was 1166.67 x 3 twice plus 820.10 x 7,
    which in binary float lands on 12740.720000000001 and rendered as a
    17-digit number on the dashboard."""
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[
            _row(key="a", label="A", man_days=6, priced_man_days=6, total_cost=Decimal("7000.02")),
            _row(key="b", label="B", man_days=7, priced_man_days=7, total_cost=Decimal("5740.70")),
        ],
        generated_at=GENERATED,
    )
    assert statement["total_cost"] == Decimal("12740.72")
    assert isinstance(statement["total_cost"], Decimal)


def test_a_group_with_no_wage_recorded_contributes_man_days_but_no_cost():
    """A partly-priced report must understate cost, never invent one."""
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[
            _row(key="paid", label="Paid", man_days=4, priced_man_days=4, total_cost=Decimal("3200.00")),
            _row(key="free", label="Unpriced", man_days=6, priced_man_days=0, total_cost=Decimal("0")),
        ],
        generated_at=GENERATED,
    )
    assert statement["total_cost"] == Decimal("3200.00")
    assert statement["total_man_days"] == 10
    assert statement["priced_man_days"] == 4
    assert statement["unpriced_man_days"] == 6


def test_average_wage_ignores_unpriced_man_days_rather_than_counting_them_as_zero():
    """10 workers at 800 alongside 10 unpriced is an average of 800 -- the
    rate that was actually paid. Dividing by all 20 would report 400, which
    nobody earned."""
    assert average_daily_wage(Decimal("8000.00"), 10) == Decimal("800.00")
    assert average_daily_wage(Decimal("8000.00"), 20) == Decimal("400.00")

    statement = build_statement(
        report_type="trade_breakdown",
        rows=[
            _row(key="paid", man_days=10, priced_man_days=10, total_cost=Decimal("8000.00")),
            _row(key="free", man_days=10, priced_man_days=0, total_cost=Decimal("0")),
        ],
        generated_at=GENERATED,
    )
    assert statement["avg_daily_wage"] == Decimal("800.00")


def test_nothing_priced_yields_a_zero_average_not_a_division_error():
    assert average_daily_wage(Decimal("0"), 0) == Decimal("0.00")


def test_an_empty_statement_reports_zeroes_not_a_default_wage():
    """The old code fell back to 800/day when there was no attendance at all,
    so an empty system displayed a populated-looking statement."""
    statement = build_statement(report_type="trade_breakdown", rows=[], generated_at=GENERATED)
    assert statement["rows"] == []
    assert statement["total_cost"] == Decimal("0.00")
    assert statement["total_man_days"] == 0
    assert statement["avg_daily_wage"] == Decimal("0.00")


# --- Days worked ----------------------------------------------------------

def test_days_worked_is_passed_through_and_never_derived_from_man_days():
    """One worker on 3 days across 5 lines is 3 days worked, not 5. The value
    comes from COUNT(DISTINCT occurred_date) and must not be recomputed here."""
    statement = build_statement(
        report_type="worker_wages",
        rows=[_row(key="w1", label="Ravi", man_days=5, priced_man_days=5, days_worked=3)],
        generated_at=GENERATED,
    )
    assert statement["rows"][0]["days_worked"] == 3
    assert statement["rows"][0]["man_days"] == 5


def test_first_and_last_seen_survive_into_the_row():
    statement = build_statement(
        report_type="worker_wages",
        rows=[
            _row(
                key="w1",
                label="Ravi",
                first_date=datetime.date(2026, 7, 1),
                last_date=datetime.date(2026, 7, 20),
            )
        ],
        generated_at=GENERATED,
    )
    assert statement["rows"][0]["first_date"] == datetime.date(2026, 7, 1)
    assert statement["rows"][0]["last_date"] == datetime.date(2026, 7, 20)


# --- Temporary workers ----------------------------------------------------

def test_a_temporary_worker_keyed_by_name_appears_like_any_other():
    """Temporary workers have no register row, so their key is the name
    rather than a worker_id. They are 30-60% of construction attendance and
    must not be a degraded path (principle P3)."""
    statement = build_statement(
        report_type="worker_wages",
        rows=[
            _row(key="c0ffee00-0000-4000-8000-000000000000", label="Ravi (permanent)"),
            _row(key="akhilesh", label="Akhilesh", total_cost=Decimal("9000.00")),
        ],
        generated_at=GENERATED,
    )
    titles = [r["title"] for r in statement["rows"]]
    assert "Akhilesh" in titles
    assert "Ravi (permanent)" in titles


def test_a_worker_line_with_no_name_is_labelled_not_dropped_or_blank():
    statement = build_statement(
        report_type="worker_wages",
        rows=[_row(key="x", label=None)],
        generated_at=GENERATED,
    )
    assert statement["rows"][0]["title"] == "Unnamed worker"


# --- Labelling ------------------------------------------------------------

def test_a_missing_trade_says_it_was_not_recorded_rather_than_naming_a_trade():
    """"General Labor" reads as a fact about the worker. It is not one -- the
    line simply carried no trade."""
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[_row(key="", label=None)],
        generated_at=GENERATED,
    )
    assert statement["rows"][0]["title"] == UNSPECIFIED_TRADE


def test_a_missing_contractor_says_so_rather_than_asserting_direct_payroll():
    statement = build_statement(
        report_type="subcontractor_ledger",
        rows=[_row(key="", label="   ")],
        generated_at=GENERATED,
    )
    assert statement["rows"][0]["title"] == UNSPECIFIED_CONTRACTOR


# --- Percentages ----------------------------------------------------------

def test_percentages_are_shares_of_the_statement_total():
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[
            _row(key="a", total_cost=Decimal("7500.00")),
            _row(key="b", total_cost=Decimal("2500.00")),
        ],
        generated_at=GENERATED,
    )
    by_key = {r["id"]: r["percentage"] for r in statement["rows"]}
    assert by_key["a"] == Decimal("75.00")
    assert by_key["b"] == Decimal("25.00")


def test_percentage_of_an_unpriced_statement_is_zero_not_a_hundred():
    """An org that records attendance without wages must not read as 100%
    of a cost that is zero."""
    assert contribution_percentage(Decimal("0"), Decimal("0")) == Decimal("0.00")


# --- Report definitions ---------------------------------------------------

def test_each_report_type_maps_to_its_grouping():
    assert resolve_group_by("trade_breakdown") == "trade"
    assert resolve_group_by("subcontractor_ledger") == "contractor"
    assert resolve_group_by("daily_attendance") == "date"
    assert resolve_group_by("worker_wages") == "worker"


def test_an_unknown_report_type_falls_back_instead_of_failing():
    """An older dashboard build asking for a retired type should still get a
    truthful statement rather than a 500."""
    assert resolve_group_by("nonsense") == "trade"
    statement = build_statement(report_type="nonsense", rows=[], generated_at=GENERATED)
    assert statement["report_type"] == "trade_breakdown"


def test_cost_grouped_reports_lead_with_the_largest_spend():
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[
            _row(key="small", total_cost=Decimal("100.00")),
            _row(key="big", total_cost=Decimal("9000.00")),
        ],
        generated_at=GENERATED,
    )
    assert [r["id"] for r in statement["rows"]] == ["big", "small"]


def test_the_daily_report_reads_chronologically_not_by_cost():
    """A list of dates ordered by spend is unreadable as a daily log."""
    statement = build_statement(
        report_type="daily_attendance",
        rows=[
            _row(key="2026-07-03", label="2026-07-03", total_cost=Decimal("100.00"),
                 first_date=datetime.date(2026, 7, 3)),
            _row(key="2026-07-01", label="2026-07-01", total_cost=Decimal("9000.00"),
                 first_date=datetime.date(2026, 7, 1)),
        ],
        generated_at=GENERATED,
    )
    assert [r["id"] for r in statement["rows"]] == ["2026-07-01", "2026-07-03"]


def test_the_applied_date_range_is_echoed_back():
    """So the page can caption what was actually filtered, rather than what it
    believes it asked for."""
    statement = build_statement(
        report_type="trade_breakdown",
        rows=[],
        generated_at=GENERATED,
        date_from=datetime.date(2026, 7, 1),
        date_to=datetime.date(2026, 7, 31),
    )
    assert statement["date_from"] == datetime.date(2026, 7, 1)
    assert statement["date_to"] == datetime.date(2026, 7, 31)


def test_the_worker_statement_warns_that_headcount_groups_are_missing():
    """The per-worker report's totals are legitimately lower than every other
    report's for the same range: an unnamed "7 masons" group has nobody to
    credit a day to, so it is excluded here while still counting elsewhere.
    Production shows 71 man-days here against 263 on the trade report, and
    without the subtitle saying so that gap reads as a bug.
    """
    statement = build_statement(
        report_type="worker_wages", rows=[], generated_at=GENERATED
    )
    assert "headcount group" in statement["subtitle"].lower()


def test_the_other_statements_make_no_such_claim():
    """Only the per-worker grouping drops rows, so only it should carry the
    caveat -- an exclusion notice on a report that excludes nothing would be
    its own small untruth."""
    for report_type in ("trade_breakdown", "subcontractor_ledger", "daily_attendance"):
        statement = build_statement(
            report_type=report_type, rows=[], generated_at=GENERATED
        )
        assert "headcount group" not in statement["subtitle"].lower(), report_type
