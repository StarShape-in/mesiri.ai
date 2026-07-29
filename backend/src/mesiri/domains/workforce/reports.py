"""Labour report statements — the pure half.

Everything here operates on already-aggregated rows and does no I/O, so the
arithmetic that decides what a supervisor sees is unit-testable without a
database. The SQL that produces those rows lives in
`infrastructure/postgres/repositories/workforce.py`; the HTTP shape lives in
`domains/workforce/router.py`.

The split exists because of what these reports replaced. The dashboard used
to compute them in the browser off the *worker register*, pricing it at an
assumed 800/day and asserting a 10- or 30-day month for everyone on it
(docs/plans/labour-reports-audit.md §2.1). Attendance is the only source of
truth here: if a number cannot be derived from a recorded attendance line, it
is not produced.

Two rules carried over from `_line_totals`, and they must stay in step with
it -- the dashboard has already disagreed with the WhatsApp confirmation for
the very same report once:

1. Decimal throughout, never float.
2. A line with no wage contributes man-days but no cost, and is excluded
   from the average. Averaging over unpriced man-days would drag the rate
   toward zero and report a wage nobody was paid.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

#: Grouping key -> (title, subtitle). The keys are the wire values the
#: dashboard sends as `report_type`; they predate this module and are kept so
#: the page's existing switch keeps working.
REPORT_DEFINITIONS: dict[str, dict[str, str]] = {
    "trade_breakdown": {
        "group_by": "trade",
        "title": "Trade Cost & Man-Day Summary",
        "subtitle": "Recorded attendance grouped by trade",
        "code_prefix": "TRD",
    },
    "subcontractor_ledger": {
        "group_by": "contractor",
        "title": "Contractor Cost Summary",
        "subtitle": "Recorded attendance grouped by contractor",
        "code_prefix": "CON",
    },
    "daily_attendance": {
        "group_by": "date",
        "title": "Daily Attendance Summary",
        "subtitle": "Recorded attendance grouped by day",
        "code_prefix": "ATT",
    },
    "worker_wages": {
        "group_by": "worker",
        "title": "Labour Cost by Worker",
        # Says the quiet part out loud: this statement's totals are lower than
        # every other report's for the same range, because a headcount group
        # ("7 masons") has nobody to credit a day to and is excluded here while
        # still counting everywhere else. Without this note the difference
        # reads as a bug.
        "subtitle": (
            "Recorded attendance grouped by worker, permanent and temporary. "
            "Excludes unnamed headcount groups."
        ),
        "code_prefix": "WRK",
    },
}

DEFAULT_REPORT_TYPE = "trade_breakdown"

#: Shown instead of an empty grouping key. Deliberately not "General Labor" or
#: "Direct Payroll" -- those read as facts about the worker. These say only
#: that the attendance line carried no value, which is all that is known.
UNSPECIFIED_TRADE = "Trade not recorded"
UNSPECIFIED_CONTRACTOR = "No contractor recorded"

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class AggregateRow:
    """One group's totals, straight from SQL.

    `man_days` counts every person-day in the group. `priced_man_days` counts
    only those whose line carried a wage -- the two differ whenever a report
    was recorded without pay rates, and conflating them is what produces an
    average nobody earned.
    """

    key: str
    label: str | None
    man_days: int
    priced_man_days: int
    total_cost: Decimal
    days_worked: int
    first_date: datetime.date | None = None
    last_date: datetime.date | None = None
    report_count: int = 0
    contractor: str | None = None
    trade: str | None = None


def resolve_group_by(report_type: str) -> str:
    """The grouping key for a report type, defaulting rather than raising --
    an unknown type from an older dashboard build should still render
    something truthful instead of a 500."""
    definition = REPORT_DEFINITIONS.get(report_type) or REPORT_DEFINITIONS[DEFAULT_REPORT_TYPE]
    return definition["group_by"]


def average_daily_wage(total_cost: Decimal, priced_man_days: int) -> Decimal:
    """Cost divided by the man-days that actually carried a wage.

    Dividing by *all* man-days would understate the rate on any partly-priced
    report -- 10 workers at 800 with 10 more unpriced would report 400/day,
    a number no one was paid. Unpriced man-days are absent from the average,
    not zero in it.
    """
    if priced_man_days <= 0:
        return Decimal("0.00")
    return (total_cost / Decimal(priced_man_days)).quantize(_CENTS)


def contribution_percentage(row_cost: Decimal, total_cost: Decimal) -> Decimal:
    """A row's share of the statement's cost. Zero when nothing is priced --
    never a divide-by-zero, and never a fabricated 100%."""
    if total_cost <= 0:
        return Decimal("0.00")
    return (row_cost / total_cost * Decimal(100)).quantize(_CENTS)


def _display_label(group_by: str, row: AggregateRow) -> str:
    if row.label:
        label = row.label.strip()
        if label:
            return label
    if group_by == "trade":
        return UNSPECIFIED_TRADE
    if group_by == "contractor":
        return UNSPECIFIED_CONTRACTOR
    if group_by == "worker":
        return "Unnamed worker"
    return str(row.key)


def build_statement(
    *,
    report_type: str,
    rows: list[AggregateRow],
    generated_at: datetime.datetime,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> dict:
    """Turn aggregate rows into the statement the dashboard renders.

    Totals are summed from the rows themselves rather than recomputed from a
    second query, so a row can never disagree with the header above it.
    """
    definition = REPORT_DEFINITIONS.get(report_type) or REPORT_DEFINITIONS[DEFAULT_REPORT_TYPE]
    group_by = definition["group_by"]
    prefix = definition["code_prefix"]

    total_cost = sum((r.total_cost for r in rows), Decimal("0")).quantize(_CENTS)
    total_man_days = sum(r.man_days for r in rows)
    total_priced_man_days = sum(r.priced_man_days for r in rows)

    statement_rows = []
    for index, row in enumerate(_ordered(group_by, rows), start=1):
        statement_rows.append(
            {
                "id": row.key,
                "code": f"{prefix}-{index:03d}",
                "title": _display_label(group_by, row),
                "category": row.trade,
                "contractor": row.contractor,
                "man_days": row.man_days,
                "priced_man_days": row.priced_man_days,
                "days_worked": row.days_worked,
                "first_date": row.first_date,
                "last_date": row.last_date,
                "report_count": row.report_count,
                "avg_daily_wage": average_daily_wage(row.total_cost, row.priced_man_days),
                "total_cost": row.total_cost.quantize(_CENTS),
                "percentage": contribution_percentage(row.total_cost, total_cost),
            }
        )

    return {
        "report_type": report_type if report_type in REPORT_DEFINITIONS else DEFAULT_REPORT_TYPE,
        "title": definition["title"],
        "subtitle": definition["subtitle"],
        "generated_at": generated_at,
        "date_from": date_from,
        "date_to": date_to,
        "total_man_days": total_man_days,
        "priced_man_days": total_priced_man_days,
        # The dashboard needs to be able to say "cost covers 40 of 55
        # man-days" rather than implying the total is complete when it is not.
        "unpriced_man_days": total_man_days - total_priced_man_days,
        "total_cost": total_cost,
        "avg_daily_wage": average_daily_wage(total_cost, total_priced_man_days),
        "rows": statement_rows,
    }


# ---------------------------------------------------------------------------
# Worker statistics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkerStatisticsInput:
    """One worker's attendance history straight from SQL.

    `trades` and `contractors` arrive as Postgres arrays that may contain
    NULLs, because the aggregate collects them without a FILTER clause.
    """

    key: str
    worker_id: str | None
    name: str | None
    days_worked: int
    attendance_count: int
    man_days: int
    priced_man_days: int
    total_earnings: Decimal
    first_seen: datetime.date | None
    last_seen: datetime.date | None
    trades: list[str | None] | None = None
    contractors: list[str | None] | None = None
    #: Only populated by the single-worker lookup -- see the repository's
    #: `include_dates`. Empty on the list endpoint, which is not a claim that
    #: the worker has no dates.
    dates_worked: list[datetime.date] | None = None


def clean_history(values: list[str | None] | None) -> list[str]:
    """Trades or contractors someone has actually worked under.

    Deduplicated case-insensitively but presented in their original spelling,
    with blanks and NULLs dropped -- a line that recorded no trade is not a
    trade called "". Sorted so the same history renders identically on every
    request.
    """
    if not values:
        return []
    seen: dict[str, str] = {}
    for value in values:
        if value is None:
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        seen.setdefault(cleaned.lower(), cleaned)
    return sorted(seen.values(), key=str.lower)


def build_worker_statistics(rows: list[WorkerStatisticsInput]) -> list[dict]:
    """Shape per-worker attendance history for the API.

    Every field here is derived from recorded attendance. There is no stored
    "days worked" to fall out of date, and nothing is editable -- which is the
    point: these are facts about what happened, not settings on a person.
    """
    statistics = []
    for row in rows:
        earnings = row.total_earnings.quantize(_CENTS)
        statistics.append(
            {
                "key": row.key,
                "worker_id": row.worker_id,
                "name": (row.name or "").strip() or "Unnamed worker",
                # A worker with no register row was never promoted. Saying so
                # is more useful than showing a blank id, and it is the cue to
                # promote them if they keep appearing.
                "is_registered": row.worker_id is not None,
                "days_worked": row.days_worked,
                "attendance_count": row.attendance_count,
                "man_days": row.man_days,
                "priced_man_days": row.priced_man_days,
                "unpriced_man_days": row.man_days - row.priced_man_days,
                "total_earnings": earnings,
                "avg_daily_wage": average_daily_wage(earnings, row.priced_man_days),
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "trades": clean_history(row.trades),
                "contractors": clean_history(row.contractors),
                # Chronological, and NULLs dropped the same way the history
                # lists are -- array_agg brings them back for rows that
                # aggregated nothing.
                "dates_worked": sorted(d for d in (row.dates_worked or []) if d is not None),
            }
        )
    # Most days worked first -- the register's most-used people are the ones a
    # supervisor scans for. Name breaks ties so the order never wobbles
    # between identical rows.
    return sorted(statistics, key=lambda s: (-s["days_worked"], s["name"].lower()))


def _ordered(group_by: str, rows: list[AggregateRow]) -> list[AggregateRow]:
    """Cost-descending for the groupings a reader scans to answer "where did
    the money go".

    The daily statement is the exception: it is read top-to-bottom as a
    ledger, so it runs oldest to newest. Ordering a list of dates by spend is
    unreadable, and sorting it newest-first would disagree with the Overview
    page's trend chart, which was already fixed once to run left-to-right
    oldest-to-newest.
    """
    if group_by == "date":
        return sorted(rows, key=lambda r: (r.first_date or datetime.date.min, r.key))
    return sorted(rows, key=lambda r: (r.total_cost, r.man_days), reverse=True)
