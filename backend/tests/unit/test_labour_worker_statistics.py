"""Worker statistics — derived from attendance, never stored.

Days worked, first/last seen, earnings and trade history are facts about the
attendance record, recomputed on read. These pin the two things that make
that safe: the arithmetic (here) and the predicate that decides whose
attendance counts (test_labour_worker_statistics_sql.py).

The rule under test throughout: if it cannot be derived from a recorded
attendance line, it is not produced. No assumed month, no default wage, no
editable "days worked" field.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from mesiri.domains.workforce.reports import (
    WorkerStatisticsInput,
    build_worker_statistics,
    clean_history,
)

JULY_1 = datetime.date(2026, 7, 1)
JULY_20 = datetime.date(2026, 7, 20)


def _input(**overrides) -> WorkerStatisticsInput:
    defaults = dict(
        key="ravi",
        worker_id=None,
        name="Ravi",
        days_worked=3,
        attendance_count=3,
        man_days=3,
        priced_man_days=3,
        total_earnings=Decimal("2400.00"),
        first_seen=JULY_1,
        last_seen=JULY_20,
    )
    defaults.update(overrides)
    return WorkerStatisticsInput(**defaults)


# --- Days worked ----------------------------------------------------------

def test_days_worked_and_attendance_count_are_reported_separately():
    """Someone recorded on two sites on one day is one day worked but two
    attendance records. Collapsing them would lose real information; treating
    them as the same number would overstate days."""
    stats = build_worker_statistics([_input(days_worked=5, attendance_count=7)])[0]
    assert stats["days_worked"] == 5
    assert stats["attendance_count"] == 7


def test_days_worked_is_never_inferred_from_man_days():
    stats = build_worker_statistics([_input(days_worked=2, man_days=9)])[0]
    assert stats["days_worked"] == 2


def test_first_and_last_seen_come_through_unchanged():
    stats = build_worker_statistics([_input()])[0]
    assert stats["first_seen"] == JULY_1
    assert stats["last_seen"] == JULY_20


def test_a_worker_seen_once_has_the_same_first_and_last_date():
    stats = build_worker_statistics(
        [_input(days_worked=1, first_seen=JULY_1, last_seen=JULY_1)]
    )[0]
    assert stats["first_seen"] == stats["last_seen"] == JULY_1


# --- Earnings -------------------------------------------------------------

def test_earnings_stay_decimal_exact():
    stats = build_worker_statistics(
        [_input(total_earnings=Decimal("12740.72"), priced_man_days=11)]
    )[0]
    assert stats["total_earnings"] == Decimal("12740.72")
    assert isinstance(stats["total_earnings"], Decimal)


def test_unpriced_days_count_as_worked_but_not_as_earned():
    """Attendance recorded without a wage still happened. It must not invent
    pay, and it must not be hidden."""
    stats = build_worker_statistics(
        [_input(man_days=10, priced_man_days=6, total_earnings=Decimal("4800.00"))]
    )[0]
    assert stats["man_days"] == 10
    assert stats["priced_man_days"] == 6
    assert stats["unpriced_man_days"] == 4
    assert stats["total_earnings"] == Decimal("4800.00")
    assert stats["avg_daily_wage"] == Decimal("800.00")


def test_a_worker_with_no_wage_ever_recorded_earns_zero_not_a_default():
    stats = build_worker_statistics(
        [_input(man_days=4, priced_man_days=0, total_earnings=Decimal("0"))]
    )[0]
    assert stats["total_earnings"] == Decimal("0.00")
    assert stats["avg_daily_wage"] == Decimal("0.00")


# --- Temporary workers ----------------------------------------------------

def test_a_worker_with_no_register_row_is_flagged_unregistered_not_dropped():
    """Temporary workers are 30-60% of construction attendance. Their history
    is as real as anyone's; only their register status differs."""
    stats = build_worker_statistics([_input(key="akhilesh", worker_id=None)])[0]
    assert stats["is_registered"] is False
    assert stats["name"] == "Ravi"


def test_a_registered_worker_carries_the_register_id():
    stats = build_worker_statistics(
        [_input(worker_id="c0ffee00-0000-4000-8000-000000000000")]
    )[0]
    assert stats["is_registered"] is True
    assert stats["worker_id"] == "c0ffee00-0000-4000-8000-000000000000"


def test_a_nameless_line_is_labelled_rather_than_rendered_blank():
    stats = build_worker_statistics([_input(name=None)])[0]
    assert stats["name"] == "Unnamed worker"

    stats = build_worker_statistics([_input(name="   ")])[0]
    assert stats["name"] == "Unnamed worker"


# --- Trade and contractor history -----------------------------------------

def test_history_drops_nulls_and_blanks_that_arrive_from_the_aggregate():
    """array_agg returns NULLs for lines that recorded no trade. A blank is
    not a trade called ""."""
    assert clean_history(["mason", None, "", "  "]) == ["mason"]
    assert clean_history(None) == []
    assert clean_history([]) == []


def test_history_deduplicates_case_insensitively_but_keeps_the_spelling():
    assert clean_history(["Mason", "mason", "MASON"]) == ["Mason"]


def test_history_is_sorted_so_the_same_worker_renders_identically_each_time():
    assert clean_history(["welder", "Mason", "helper"]) == ["helper", "Mason", "welder"]


def test_a_worker_who_changed_trade_shows_both():
    """A helper promoted to mason has worked as both. The register holds only
    the current trade; the attendance record holds the history."""
    stats = build_worker_statistics([_input(trades=["helper", "mason"])])[0]
    assert stats["trades"] == ["helper", "mason"]


def test_contractor_history_works_the_same_way():
    stats = build_worker_statistics(
        [_input(contractors=["Kumar Agency", None, "kumar agency", "Reddy Labour"])]
    )[0]
    assert stats["contractors"] == ["Kumar Agency", "Reddy Labour"]


# --- Ordering -------------------------------------------------------------

def test_the_most_frequently_present_workers_come_first():
    stats = build_worker_statistics(
        [
            _input(key="rare", name="Rare", days_worked=1),
            _input(key="often", name="Often", days_worked=20),
        ]
    )
    assert [s["name"] for s in stats] == ["Often", "Rare"]


def test_equal_days_are_broken_by_name_so_the_order_never_wobbles():
    stats = build_worker_statistics(
        [
            _input(key="b", name="Zahir", days_worked=4),
            _input(key="a", name="Anand", days_worked=4),
        ]
    )
    assert [s["name"] for s in stats] == ["Anand", "Zahir"]


def test_no_attendance_at_all_produces_no_rows():
    assert build_worker_statistics([]) == []
