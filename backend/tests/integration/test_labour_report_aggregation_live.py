"""Labour report aggregation against a real Postgres.

The unit tests either pin the compiled SQL predicate or exercise the pure
arithmetic. Neither proves that Postgres, given real rows, produces the
numbers the statement then formats. These do — and in particular they are the
only place that proves the SQL aggregate and `_line_totals` (which the
Attendance page uses) agree on the same attendance, which is the guarantee
that stops the Reports page and the Attendance page disagreeing about the
same day.

Run with a live database:
    pytest backend/tests/integration/test_labour_report_aggregation_live.py -m integration
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.workforce import (
    PostgresWorkforceReadRepository,
)

pytestmark = pytest.mark.integration

DAY_ONE = datetime.date(2026, 7, 1)
DAY_TWO = datetime.date(2026, 7, 2)
DAY_THREE = datetime.date(2026, 7, 3)


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    """One organization, three days of attendance, covering every case the
    aggregation has to get right: a permanent worker, a temporary worker with
    no register row, a headcount group, an unpriced line, and a superseded
    report that must not be counted.

    Only rows this fixture created are removed at teardown -- never a blanket
    DELETE of tables it does not own.
    """
    org = uuid.uuid4()
    user = uuid.uuid4()
    project = uuid.uuid4()
    site = uuid.uuid4()
    permanent_worker = uuid.uuid4()

    report_day_one = uuid.uuid4()
    report_day_two = uuid.uuid4()
    superseded = uuid.uuid4()
    replacement = uuid.uuid4()
    report_ids = [report_day_one, report_day_two, superseded, replacement]

    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at) VALUES (:id, :name, 'local', 'default', 'active', now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": org, "name": f"labour-reports-{org}"},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, created_at) "
                "VALUES (:id, :org, :email, 'x', 'Test', 'admin', 'active', now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": user, "org": org, "email": f"{user}@example.test"},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, status, created_at) "
                "VALUES (:id, :org, 'Reports Project', 'active', now()) ON CONFLICT DO NOTHING"
            ),
            {"id": project, "org": org},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO sites (id, project_id, organization_id, name, status, created_at) "
                "VALUES (:id, :project, :org, 'Reports Site', 'active', now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": site, "project": project, "org": org},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO workforce_workers "
                "(id, organization_id, name, trade, worker_type, default_daily_wage, "
                " status, created_at, created_by, updated_at) "
                "VALUES (:id, :org, 'Ravi', 'mason', 'permanent', 2000, 'active', "
                "        now(), :user, now())"
            ),
            {"id": permanent_worker, "org": org, "user": user},
        )

        async def _report(report_id, occurred, corrects=None):
            await conn.execute(
                sa.text(
                    "INSERT INTO labour_attendance_reports "
                    "(id, organization_id, project_id, site_id, occurred_date, "
                    " recorded_via, corrects_report_id, created_at, created_by) "
                    "VALUES (:id, :org, :project, :site, :occurred, 'whatsapp_text', "
                    "        :corrects, now(), :user)"
                ),
                {
                    "id": report_id,
                    "org": org,
                    "project": project,
                    "site": site,
                    "occurred": occurred,
                    "corrects": corrects,
                    "user": user,
                },
            )

        async def _line(report_id, *, worker_id=None, name=None, trade=None,
                        headcount=1, wage=None, contractor=None):
            await conn.execute(
                sa.text(
                    "INSERT INTO labour_attendance_lines "
                    "(id, report_id, worker_id, worker_name, trade, headcount, "
                    " daily_wage, contractor, created_at) "
                    "VALUES (:id, :report, :worker, :name, :trade, :headcount, "
                    "        :wage, :contractor, now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "report": report_id,
                    "worker": worker_id,
                    "name": name,
                    "trade": trade,
                    "headcount": headcount,
                    "wage": wage,
                    "contractor": contractor,
                },
            )

        # Day one: a permanent mason and a temporary helper with no register row.
        await _report(report_day_one, DAY_ONE)
        await _line(report_day_one, worker_id=permanent_worker, name="Ravi",
                    trade="mason", wage=Decimal("1166.67"), contractor="Kumar Agency")
        await _line(report_day_one, name="Akhilesh", trade="helper",
                    wage=Decimal("820.10"))

        # Day two: the same permanent worker again, a headcount group, and a
        # line recorded with no wage at all.
        await _report(report_day_two, DAY_TWO)
        await _line(report_day_two, worker_id=permanent_worker, name="Ravi",
                    trade="mason", wage=Decimal("1166.67"), contractor="Kumar Agency")
        await _line(report_day_two, trade="mason", headcount=7,
                    wage=Decimal("820.10"))
        await _line(report_day_two, name="Unpaid Person", trade="helper", wage=None)

        # Day three: a report the supervisor re-sent. Only the replacement counts.
        await _report(superseded, DAY_THREE)
        await _line(superseded, name="Ghost", trade="mason", headcount=16,
                    wage=Decimal("1000.00"))
        await _report(replacement, DAY_THREE, corrects=superseded)
        await _line(replacement, name="Ghost", trade="mason", headcount=18,
                    wage=Decimal("1000.00"))

    yield {
        "org": org,
        "project": project,
        "site": site,
        "permanent_worker": permanent_worker,
        "report_ids": report_ids,
    }

    async with engine.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM labour_attendance_lines WHERE report_id = ANY(:ids)"),
            {"ids": report_ids},
        )
        await conn.execute(
            sa.text("DELETE FROM labour_attendance_reports WHERE id = ANY(:ids)"),
            {"ids": report_ids},
        )
        await conn.execute(
            sa.text("DELETE FROM workforce_workers WHERE organization_id = :org"), {"org": org}
        )
        await conn.execute(sa.text("DELETE FROM sites WHERE id = :id"), {"id": site})
        await conn.execute(sa.text("DELETE FROM projects WHERE id = :id"), {"id": project})
        await conn.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": user})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org})


async def _rows(engine, scenario, group_by, **kwargs):
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        return await repo.aggregate_attendance(
            organization_id=scenario["org"], group_by=group_by, **kwargs
        )


async def test_superseded_report_is_not_counted(engine, scenario):
    """Day three has 16 man-days superseded by 18. The answer is 18, not 34."""
    rows = await _rows(engine, scenario, "date")
    day_three = [r for r in rows if str(r["key"]).startswith("2026-07-03")]
    assert len(day_three) == 1
    assert int(day_three[0]["man_days"]) == 18


async def test_cost_is_decimal_exact_not_binary_float(engine, scenario):
    """1166.67 x 2 + 820.10 x 8 -- the combination that previously landed on
    12740.720000000001 and rendered as a 17-digit number."""
    rows = await _rows(
        engine, scenario, "date", date_from=DAY_ONE, date_to=DAY_TWO
    )
    total = sum(Decimal(str(r["total_cost"])) for r in rows)
    assert total == Decimal("12740.72")


async def test_a_line_with_no_wage_adds_man_days_but_no_cost(engine, scenario):
    rows = await _rows(engine, scenario, "date", date_from=DAY_TWO, date_to=DAY_TWO)
    assert len(rows) == 1
    day_two = rows[0]
    # 1 permanent + 7 group + 1 unpriced
    assert int(day_two["man_days"]) == 9
    assert int(day_two["priced_man_days"]) == 8
    assert Decimal(str(day_two["total_cost"])) == Decimal("1166.67") + Decimal("820.10") * 7


async def test_a_temporary_worker_with_no_register_row_still_gets_a_line(engine, scenario):
    """Akhilesh has no workforce_workers row. Keying on worker_id alone would
    drop him entirely."""
    rows = await _rows(engine, scenario, "worker")
    labels = {(r["label"] or "").lower() for r in rows}
    assert "akhilesh" in labels


async def test_a_headcount_group_is_excluded_from_the_per_worker_report(engine, scenario):
    """"7 masons" has no identity, so it cannot be a named row -- but its cost
    must still appear in the trade totals."""
    worker_rows = await _rows(engine, scenario, "worker")
    assert all(r["label"] for r in worker_rows)

    trade_rows = await _rows(engine, scenario, "trade")
    mason = next(r for r in trade_rows if (r["label"] or "").lower() == "mason")
    # 1 (day one) + 1 + 7 (day two) + 18 (day three replacement)
    assert int(mason["man_days"]) == 27


async def test_days_worked_counts_distinct_dates_not_appearances(engine, scenario):
    """Ravi appears on two lines across two days -- two days worked."""
    rows = await _rows(engine, scenario, "worker")
    ravi = next(r for r in rows if str(r["key"]) == str(scenario["permanent_worker"]))
    assert int(ravi["days_worked"]) == 2
    assert ravi["first_date"] == DAY_ONE
    assert ravi["last_date"] == DAY_TWO


async def test_a_date_range_excludes_attendance_outside_it(engine, scenario):
    rows = await _rows(engine, scenario, "date", date_from=DAY_ONE, date_to=DAY_ONE)
    assert len(rows) == 1
    assert int(rows[0]["man_days"]) == 2


async def test_contractor_grouping_separates_named_from_unrecorded(engine, scenario):
    rows = await _rows(engine, scenario, "contractor")
    by_label = {(r["label"] or ""): r for r in rows}
    assert "Kumar Agency" in by_label
    assert int(by_label["Kumar Agency"]["man_days"]) == 2


async def test_worker_statistics_derive_days_and_earnings_from_attendance(engine, scenario):
    """Ravi worked day one and day two at 1166.67 each. Two days, 2333.34 --
    and nothing here came from his register wage of 2000."""
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        stats = await repo.worker_statistics(organization_id=scenario["org"])

    ravi = next(s for s in stats if str(s["worker_id"]) == str(scenario["permanent_worker"]))
    assert int(ravi["days_worked"]) == 2
    assert int(ravi["attendance_count"]) == 2
    assert Decimal(str(ravi["total_earnings"])) == Decimal("2333.34")
    assert ravi["first_seen"] == DAY_ONE
    assert ravi["last_seen"] == DAY_TWO


async def test_worker_statistics_include_an_unpromoted_temporary_worker(engine, scenario):
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        stats = await repo.worker_statistics(organization_id=scenario["org"])

    akhilesh = next(s for s in stats if (s["name"] or "").lower() == "akhilesh")
    assert akhilesh["worker_id"] is None
    assert int(akhilesh["days_worked"]) == 1
    assert Decimal(str(akhilesh["total_earnings"])) == Decimal("820.10")


async def test_worker_statistics_collect_every_trade_a_person_worked_under(engine, scenario):
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        stats = await repo.worker_statistics(organization_id=scenario["org"])

    ravi = next(s for s in stats if str(s["worker_id"]) == str(scenario["permanent_worker"]))
    assert "mason" in [t for t in (ravi["trades"] or []) if t]


async def test_worker_statistics_exclude_headcount_groups(engine, scenario):
    """The 7-mason group has no name, so it cannot be credited to anyone."""
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        stats = await repo.worker_statistics(organization_id=scenario["org"])

    assert all(s["name"] or s["worker_id"] for s in stats)
    assert sum(int(s["man_days"]) for s in stats) < 27


async def test_worker_statistics_ignore_a_superseded_report(engine, scenario):
    """Ghost appears on both the superseded report and its replacement. The
    replacement is the only one that counts, so one day, not two."""
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        stats = await repo.worker_statistics(organization_id=scenario["org"])

    ghost = next(s for s in stats if (s["name"] or "").lower() == "ghost")
    assert int(ghost["days_worked"]) == 1
    assert int(ghost["man_days"]) == 18


async def test_the_aggregate_agrees_with_the_per_report_totals(engine, scenario):
    """The guarantee that keeps the Reports page and the Attendance page from
    disagreeing about the same attendance: whatever list_reports totals for a
    day, the aggregate must total too."""
    async with engine.connect() as conn:
        repo = PostgresWorkforceReadRepository(conn)
        reports, _ = await repo.list_reports(
            organization_id=scenario["org"], project_ids=None, limit=100
        )
        aggregate = await repo.aggregate_attendance(
            organization_id=scenario["org"], group_by="date"
        )

    per_report_headcount = sum(int(r["total_headcount"]) for r in reports)
    per_report_cost = sum(Decimal(str(r["total_cost"])) for r in reports)

    aggregate_headcount = sum(int(r["man_days"]) for r in aggregate)
    aggregate_cost = sum(Decimal(str(r["total_cost"])) for r in aggregate)

    assert aggregate_headcount == per_report_headcount
    assert aggregate_cost == per_report_cost
