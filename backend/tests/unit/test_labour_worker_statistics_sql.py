"""The predicate deciding whose attendance counts toward worker statistics.

Same approach as test_labour_supersede.py: compile the statement and assert
on the SQL, so the filtering rules are pinned without a live Postgres. The
arithmetic performed on the resulting rows is covered in
test_labour_worker_statistics.py.
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
WORKER = uuid.UUID("55555555-5555-4555-8555-555555555555")


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


async def _sql(**kwargs) -> str:
    conn = _Recorder([_Result([])])
    repo = PostgresWorkforceReadRepository(conn)
    await repo.worker_statistics(organization_id=ORG, **kwargs)
    return conn.statements[0]


async def test_superseded_reports_do_not_inflate_anyone_s_history():
    """A re-sent report must not give a worker a second day, or double their
    earnings for a day they worked once."""
    sql = await _sql()
    assert "corrects_report_id" in sql
    assert "NOT IN" in sql.upper()


async def test_statistics_are_never_read_from_the_register():
    """The whole point: days worked and earnings come from attendance lines.
    Touching workforce_workers here would reintroduce the register as a source
    of cost."""
    sql = await _sql()
    assert "workforce_workers" not in sql
    assert "default_daily_wage" not in sql


async def test_days_worked_counts_distinct_dates_and_attendance_counts_reports():
    sql = await _sql()
    assert "count(DISTINCT labour_attendance_reports.occurred_date)" in sql
    assert "count(DISTINCT labour_attendance_lines.report_id)" in sql


async def test_earnings_use_the_wage_recorded_on_the_line():
    sql = await _sql()
    assert "labour_attendance_lines.daily_wage" in sql


async def test_temporary_workers_are_keyed_by_name_when_they_have_no_register_id():
    sql = await _sql()
    assert "coalesce" in sql.lower()
    assert "worker_name" in sql


async def test_headcount_groups_are_excluded_having_nobody_to_credit():
    sql = await _sql()
    assert "worker_id IS NOT NULL" in sql
    assert "worker_name IS NOT NULL" in sql


async def test_trade_and_contractor_history_are_collected_per_worker():
    sql = await _sql()
    assert "array_agg" in sql.lower()
    assert sql.lower().count("array_agg") == 2


async def test_a_single_worker_lookup_narrows_to_that_worker():
    sql = await _sql(worker_id=WORKER)
    assert "labour_attendance_lines.worker_id =" in sql


async def test_scope_and_date_filters_reach_the_query():
    sql = await _sql(
        project_ids={PRJ},
        site_id=SITE,
        date_from=datetime.date(2026, 7, 1),
        date_to=datetime.date(2026, 7, 31),
    )
    assert "project_id IN" in sql
    assert "site_id =" in sql
    assert "occurred_date >=" in sql
    assert "occurred_date <=" in sql


async def test_the_organization_is_always_constrained():
    assert "organization_id" in await _sql()
