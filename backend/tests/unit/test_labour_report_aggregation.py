"""The SQL behind the Labour report statements.

Follows test_labour_supersede.py's approach: capture the compiled statement
and assert on the predicate, so the rules that decide *which* attendance is
counted are pinned without needing a live Postgres. The arithmetic performed
on the resulting rows is covered in test_labour_report_statements.py; the
end-to-end numbers are covered by
backend/tests/integration/test_labour_report_aggregation_live.py.
"""

from __future__ import annotations

import datetime
import uuid

from mesiri.infrastructure.postgres.repositories.workforce import (
    PostgresWorkforceReadRepository,
)

ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
PRJ = uuid.UUID("33333333-3333-4333-8333-333333333333")
SITE = uuid.UUID("44444444-4444-4444-8444-444444444444")


class _Recorder:
    def __init__(self, results):
        self.statements: list[str] = []
        self._results = list(results)

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(str(statement.compile(compile_kwargs={"literal_binds": False})))
        return self._results.pop(0)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


async def _aggregate(**kwargs) -> str:
    conn = _Recorder([_Result([])])
    repo = PostgresWorkforceReadRepository(conn)
    await repo.aggregate_attendance(organization_id=ORG, **kwargs)
    return conn.statements[0]


# --- Superseded attendance ------------------------------------------------

async def test_superseded_reports_are_excluded_from_every_grouping():
    """The re-sent-report bug in its most dangerous form. A supervisor who
    forgets someone re-sends the whole list, creating a second immutable row;
    counting both made 18 workers read as 34 man-days. list_reports already
    excludes them, and an aggregate that forgot to would silently reinflate
    every cost figure on the Reports page.
    """
    for group_by in ("trade", "contractor", "date", "worker"):
        sql = await _aggregate(group_by=group_by)
        assert "corrects_report_id" in sql, group_by
        assert "NOT IN" in sql.upper(), group_by


async def test_superseded_reports_can_be_opted_back_in_for_audit():
    sql = await _aggregate(group_by="trade", include_superseded=True)
    assert "corrects_report_id" not in sql


# --- Date filtering -------------------------------------------------------

async def test_a_date_range_filters_on_the_date_the_work_happened():
    """occurred_date, not created_at -- attendance for last Tuesday sent this
    morning belongs to last Tuesday."""
    sql = await _aggregate(
        group_by="trade",
        date_from=datetime.date(2026, 7, 1),
        date_to=datetime.date(2026, 7, 31),
    )
    assert "occurred_date >=" in sql
    assert "occurred_date <=" in sql


async def test_an_open_ended_range_only_constrains_the_end_given():
    sql = await _aggregate(group_by="trade", date_from=datetime.date(2026, 7, 1))
    assert "occurred_date >=" in sql
    assert "occurred_date <=" not in sql


async def test_no_range_applies_no_date_predicate():
    sql = await _aggregate(group_by="trade")
    assert "occurred_date >=" not in sql
    assert "occurred_date <=" not in sql


# --- Scope ----------------------------------------------------------------

async def test_the_organization_is_always_constrained():
    sql = await _aggregate(group_by="trade")
    assert "organization_id" in sql


async def test_project_and_site_scope_reach_the_query():
    sql = await _aggregate(group_by="trade", project_ids={PRJ}, site_id=SITE)
    assert "project_id IN" in sql
    assert "site_id =" in sql


# --- Cost and man-days ----------------------------------------------------

async def test_cost_comes_from_the_wage_on_the_attendance_line():
    """Never from workforce_workers.default_daily_wage -- editing a worker's
    wage next month must not rewrite what last month cost."""
    sql = await _aggregate(group_by="trade")
    assert "labour_attendance_lines.daily_wage" in sql
    assert "default_daily_wage" not in sql
    assert "workforce_workers" not in sql


async def test_days_worked_counts_distinct_dates_not_lines():
    sql = await _aggregate(group_by="worker")
    assert "count(DISTINCT labour_attendance_reports.occurred_date)" in sql


async def test_unpriced_lines_are_counted_separately_from_priced_ones():
    """So the average can divide by the man-days that actually carried a wage
    rather than dragging the rate toward zero."""
    sql = await _aggregate(group_by="trade")
    assert "daily_wage IS NOT NULL" in sql


# --- Grouping -------------------------------------------------------------

async def test_each_grouping_buckets_by_its_own_column():
    assert "GROUP BY" in (await _aggregate(group_by="trade")).upper()
    assert "trade" in await _aggregate(group_by="trade")
    assert "contractor" in await _aggregate(group_by="contractor")
    assert "occurred_date" in await _aggregate(group_by="date")


async def test_trades_are_bucketed_case_insensitively():
    """"Mason" and "mason " are one trade, not two rows splitting the cost."""
    sql = await _aggregate(group_by="trade")
    assert "lower(trim(" in sql.lower()


# --- Temporary workers ----------------------------------------------------

async def test_the_worker_grouping_keys_on_name_when_there_is_no_register_id():
    """A temporary worker has worker_id NULL. Keying on worker_id alone would
    drop every one of them -- 30-60% of construction attendance."""
    sql = await _aggregate(group_by="worker")
    assert "coalesce" in sql.lower()
    assert "worker_name" in sql
    assert "worker_id" in sql


async def test_headcount_groups_are_left_out_of_the_per_worker_report_only():
    """"10 masons" has no identity to attribute a day to, so it cannot be a
    named row -- but it must still count toward the trade and contractor
    totals, which have no such predicate."""
    worker_sql = await _aggregate(group_by="worker")
    assert "worker_name IS NOT NULL" in worker_sql

    trade_sql = await _aggregate(group_by="trade")
    assert "worker_name IS NOT NULL" not in trade_sql
