"""A re-sent attendance report must not double the day's totals.

Reported by Alan. Attendance is immutable by design (P5): a supervisor who
forgets someone re-sends the whole list, which creates a second row for the
same site and day rather than editing the first. Nothing downstream knew
that, so a day of 18 workers showed as 16 + 18 = 34 man-days with cost
inflated to match.

`corrects_report_id` was reserved in migration 0371 for exactly this and was
never written or read by anything. These pin the read half: a report that
another report corrects is excluded from lists and totals, while staying
readable for audit.
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
    """Captures the compiled SQL of each SELECT so the tests can assert on the
    predicate rather than on a mocked result."""

    def __init__(self, results):
        self.statements: list[str] = []
        self._results = list(results)

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(
            str(statement.compile(compile_kwargs={"literal_binds": False}))
        )
        return self._results.pop(0)


class _Result:
    def __init__(self, rows, scalar=0):
        self._rows = rows
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._scalar


async def test_list_reports_excludes_superseded_by_default():
    conn = _Recorder([_Result([], scalar=0), _Result([])])
    repo = PostgresWorkforceReadRepository(conn)
    await repo.list_reports(organization_id=ORG, project_ids=None)

    count_sql = conn.statements[0]
    assert "corrects_report_id" in count_sql, count_sql
    assert "NOT IN" in count_sql.upper(), count_sql


async def test_include_superseded_opt_in_drops_the_exclusion():
    """Audit views need the full history, so the filter must be opt-out."""
    conn = _Recorder([_Result([], scalar=0), _Result([])])
    repo = PostgresWorkforceReadRepository(conn)
    await repo.list_reports(
        organization_id=ORG, project_ids=None, include_superseded=True
    )
    assert "corrects_report_id" not in conn.statements[0]


async def test_find_existing_report_for_day_matches_a_null_site_as_its_own_bucket():
    """A NULL site_id must compare with IS NULL, not `= NULL` (always false),
    or a project with no named site would never detect its own duplicate."""
    conn = _Recorder([_Result([])])
    repo = PostgresWorkforceReadRepository(conn)
    found = await repo.find_existing_report_for_day(
        ORG, project_id=PRJ, site_id=None, occurred_date=datetime.date(2026, 7, 27)
    )
    assert found is None
    assert "IS NULL" in conn.statements[0].upper()


async def test_find_existing_report_for_day_returns_totals_for_the_warning():
    """The warning has to say what is already on record, so the lookup carries
    the existing report's headcount and cost."""
    report_id = uuid.uuid4()
    report_row = {
        "id": report_id,
        "organization_id": ORG,
        "project_id": PRJ,
        "site_id": SITE,
        "occurred_date": datetime.date(2026, 7, 27),
        "recorded_via": "whatsapp_text",
        "notes": None,
        "corrects_report_id": None,
        "correlation_id": None,
        "created_at": None,
        "created_by": None,
    }
    lines = [
        {"headcount": 4, "daily_wage": 900},
        {"headcount": 12, "daily_wage": 700},
    ]
    conn = _Recorder([_Result([report_row]), _Result(lines)])
    repo = PostgresWorkforceReadRepository(conn)

    found = await repo.find_existing_report_for_day(
        ORG, project_id=PRJ, site_id=SITE, occurred_date=datetime.date(2026, 7, 27)
    )
    assert found is not None
    assert found["id"] == report_id
    assert found["total_headcount"] == 16
    assert str(found["total_cost"]) == "12000.00"
