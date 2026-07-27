"""Money must reach the browser as a JSON *number*, and be Decimal-exact.

Reported by Alan: the labour KPI cards showed obviously-wrong money. Two
independent defects combined to produce it, and neither was caught because
every existing test asserted on the repository dict or the model instance --
never on the serialized HTTP body, which is the only place either one is
visible.

1. A bare `Decimal` response field serializes to a JSON *string*. The
   dashboard sums with `+`, so "4800.00" + "3600.00" concatenated into
   "04800.003600.00" and rendered as Rs 04800.003600.00. Anything dividing
   by it (average wage, % contribution) got NaN.

2. `_line_totals` accumulated in binary float, so an ordinary mixed-wage
   report produced 12740.720000000001 and that full repr reached the UI.

These tests assert on the wire format specifically. A regression in either
one fails here rather than in production.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mesiri.domains.workforce.router import LabourAttendanceReportSummaryResponse
from mesiri.infrastructure.postgres.repositories.workforce import _line_totals

ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
PRJ = uuid.UUID("33333333-3333-4333-8333-333333333333")
REPORT_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


def _summary(total_cost: Decimal) -> LabourAttendanceReportSummaryResponse:
    return LabourAttendanceReportSummaryResponse(
        id=REPORT_ID,
        organization_id=ORG,
        project_id=PRJ,
        site_id=None,
        occurred_date=datetime.date(2026, 7, 27),
        recorded_via="whatsapp_text",
        notes=None,
        line_count=2,
        total_headcount=13,
        total_cost=total_cost,
    )


def _serve(model: LabourAttendanceReportSummaryResponse) -> dict:
    """Round-trip through a real FastAPI response, exactly as the app does."""
    app = FastAPI()

    @app.get("/r", response_model=LabourAttendanceReportSummaryResponse)
    async def _r():  # pragma: no cover - trivial
        return model

    return TestClient(app).get("/r").json()


def test_total_cost_serializes_as_a_json_number_not_a_string():
    """The one assertion that would have caught the concatenation bug."""
    body = _serve(_summary(Decimal("4800.00")))
    assert isinstance(body["total_cost"], (int, float)), body["total_cost"]
    assert body["total_cost"] == 4800.00


def test_summing_two_serialized_costs_adds_rather_than_concatenates():
    """Reproduces the exact dashboard reduce that rendered 04800.003600.00."""
    first = _serve(_summary(Decimal("4800.00")))["total_cost"]
    second = _serve(_summary(Decimal("3600.00")))["total_cost"]
    assert first + second == 8400.00


def test_line_totals_are_decimal_exact_not_binary_float():
    """3x1166.67 + 3x1166.67 + 7x820.10 -- the mixed-wage case that produced
    12740.720000000001 under float accumulation."""
    headcount, cost = _line_totals(
        [
            {"headcount": 3, "daily_wage": Decimal("1166.67")},
            {"headcount": 3, "daily_wage": Decimal("1166.67")},
            {"headcount": 7, "daily_wage": Decimal("820.10")},
        ]
    )
    assert headcount == 13
    assert cost == Decimal("12740.72")
    assert str(cost) == "12740.72"


def test_a_line_without_a_wage_is_skipped_rather_than_counted_as_zero():
    """P9 tradeoff: a partially-priced report understates cost. Pinned so the
    behaviour is a decision, not an accident."""
    headcount, cost = _line_totals(
        [
            {"headcount": 2, "daily_wage": Decimal("500.00")},
            {"headcount": 5, "daily_wage": None},
        ]
    )
    assert headcount == 7
    assert cost == Decimal("1000.00")
