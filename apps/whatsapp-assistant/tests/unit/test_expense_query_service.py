"""runtime/expense_query_service.py's pure helpers — unit tests (no DB)."""

from __future__ import annotations

import datetime
from decimal import Decimal

from runtime.expense_query_service import ExpenseQueryService, resolve_date_range


def test_today_bucket():
    start, end, label = resolve_date_range("today")
    today = datetime.date.today()
    assert start == end == today
    assert label == "today"


def test_this_week_bucket_starts_on_monday():
    start, end, label = resolve_date_range("this_week")
    assert start.weekday() == 0
    assert end == datetime.date.today()
    assert label == "this week"


def test_this_month_bucket_starts_on_the_1st():
    start, end, label = resolve_date_range("this_month")
    assert start.day == 1
    assert end == datetime.date.today()
    assert label == "this month"


def test_missing_bucket_defaults_to_this_month():
    start, _, label = resolve_date_range(None)
    assert start.day == 1
    assert label == "this month"


def test_unrecognized_bucket_defaults_to_this_month():
    start, _, label = resolve_date_range("last_year")
    assert start.day == 1
    assert label == "this month"


class _FakeExpense:
    def __init__(self, amount: str) -> None:
        self.amount = Decimal(amount)


def test_total_sums_expense_amounts():
    expenses = [_FakeExpense("100.00"), _FakeExpense("250.50")]
    assert ExpenseQueryService.total(expenses) == Decimal("350.50")


def test_total_of_empty_list_is_zero():
    assert ExpenseQueryService.total([]) == Decimal("0")
