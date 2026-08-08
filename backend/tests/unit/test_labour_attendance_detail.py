"""get_report (the attendance detail endpoint) — its return shape must be a
valid LabourAttendanceReportResponse.

Reported by Alan: the attendance detail view in the dashboard "failed to
load" while the list view worked. The cause: get_report never set
`line_count`, a required field (no default) on
LabourAttendanceReportSummaryResponse -- list_reports set it correctly, this
sibling method just never did, so every single-report fetch 500'd on FastAPI
response validation.

This had zero test coverage before now, which is exactly how it went
unnoticed. Rather than pin only the one missing field, this constructs the
real Pydantic response model from get_report's output -- the same
construction FastAPI itself performs -- so a *different* missing field in
the future fails here too, not silently in production.
"""

from __future__ import annotations

import datetime
import uuid

from mesiri.domains.workforce.router import LabourAttendanceReportResponse
from mesiri.infrastructure.postgres.repositories.workforce import (
    PostgresWorkforceReadRepository,
)

ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
PRJ = uuid.UUID("33333333-3333-4333-8333-333333333333")
REPORT_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Returns canned rows in call order: report, then lines, then
    attachments -- matching get_report's three sequential SELECTs exactly."""

    def __init__(self, report_row, line_rows, attachment_rows):
        self._queue = [
            _FakeResult([report_row] if report_row else []),
            _FakeResult(line_rows),
            _FakeResult(attachment_rows),
        ]

    async def execute(self, *args, **kwargs):
        return self._queue.pop(0)


def _report_row(**overrides):
    row = {
        "id": REPORT_ID,
        "organization_id": ORG,
        "project_id": PRJ,
        "site_id": None,
        "occurred_date": datetime.date(2026, 7, 27),
        "recorded_via": "whatsapp_text",
        "notes": None,
        "corrects_report_id": None,
        "correlation_id": "cor_1",
        "created_at": datetime.datetime.now(datetime.UTC),
        "created_by": uuid.uuid4(),
    }
    row.update(overrides)
    return row


def _line_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "report_id": REPORT_ID,
        "worker_id": None,
        "worker_name": "Ravi",
        "worker_name_original": None,
        "trade": "mason",
        "headcount": 1,
        "daily_wage": 800,
        "contractor": None,
        "activity": None,
        "created_at": datetime.datetime.now(datetime.UTC),
    }
    row.update(overrides)
    return row


async def test_get_report_output_is_a_valid_response_model():
    """The bug, pinned directly: construct the real Pydantic model from
    get_report's dict, the same way FastAPI's response_model does. Before the
    fix this raised a validation error for the missing line_count."""
    conn = _FakeConn(_report_row(), [_line_row(), _line_row(worker_name="Arun", headcount=1)], [])
    repo = PostgresWorkforceReadRepository(conn)

    item = await repo.get_report(ORG, REPORT_ID)
    assert item is not None

    response = LabourAttendanceReportResponse(**item)
    assert response.line_count == 2
    assert response.total_headcount == 2


async def test_line_count_counts_rows_not_people():
    """A headcount group is one row but several people -- line_count and
    total_headcount are deliberately different numbers."""
    conn = _FakeConn(
        _report_row(),
        [_line_row(worker_name=None, headcount=12), _line_row(worker_name="Ravi", headcount=1)],
        [],
    )
    repo = PostgresWorkforceReadRepository(conn)
    item = await repo.get_report(ORG, REPORT_ID)

    assert item["line_count"] == 2
    assert item["total_headcount"] == 13


async def test_cost_multiplies_wage_by_headcount_in_the_detail_view_too():
    conn = _FakeConn(_report_row(), [_line_row(worker_name=None, headcount=4, daily_wage=600)], [])
    repo = PostgresWorkforceReadRepository(conn)
    item = await repo.get_report(ORG, REPORT_ID)

    assert item["total_cost"] == 2400.0


async def test_a_report_with_no_lines_still_returns_a_valid_response():
    """An attendance with zero lines is a degenerate case, not one that
    should crash the detail view."""
    conn = _FakeConn(_report_row(), [], [])
    repo = PostgresWorkforceReadRepository(conn)
    item = await repo.get_report(ORG, REPORT_ID)

    response = LabourAttendanceReportResponse(**item)
    assert response.line_count == 0
    assert response.total_headcount == 0


async def test_a_missing_report_returns_none_not_an_error():
    conn = _FakeConn(None, [], [])
    repo = PostgresWorkforceReadRepository(conn)
    item = await repo.get_report(ORG, REPORT_ID)
    assert item is None


def test_an_attachment_with_no_usable_link_still_validates():
    """Reported from the dashboard: opening a report showed the totals but no
    worker names at all.

    The endpoint presigns every attachment through assert_downloadable_url,
    which *raises* when object storage hands back something unusable (a
    misconfigured provider returning memory://, or a key it no longer
    resolves). That took the whole response down -- including the worker
    names, which have nothing to do with the photos. The link is now allowed
    to be null so the attendance record still reaches the user.
    """
    payload = {
        "id": REPORT_ID,
        "organization_id": ORG,
        "project_id": PRJ,
        "site_id": None,
        "occurred_date": datetime.date(2026, 7, 28),
        "recorded_via": "whatsapp",
        "notes": None,
        "created_at": datetime.datetime(2026, 7, 28, tzinfo=datetime.UTC),
        "line_count": 1,
        "total_headcount": 3,
        "total_cost": "2400.00",
        "lines": [
            {
                "id": uuid.uuid4(),
                "worker_id": None,
                "worker_name": "Rahul Nair",
                "worker_name_original": None,
                "trade": "helper",
                "headcount": 1,
                "daily_wage": "800.00",
                "contractor": None,
                "activity": None,
            }
        ],
        "attachments": [
            {"id": uuid.uuid4(), "attachment_type": "attendance_sheet", "url": None}
        ],
    }

    response = LabourAttendanceReportResponse.model_validate(payload)

    # The point of the fix: the names survive an unusable photo link.
    assert [line.worker_name for line in response.lines] == ["Rahul Nair"]
    assert response.attachments[0].url is None
