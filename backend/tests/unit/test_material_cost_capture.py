"""Unit tests for purchase cost capture (Phase B).

The rule these all circle is that an unrecorded price must stay unrecorded.
Storing it as zero would claim the delivery was free and drag every average and
total toward nonsense -- which is exactly why application/dpr/assembly.py
refuses to report material cost at all today.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from mesiri.domains.materials.router import _resolve_costs


def test_no_price_recorded_stays_none_never_zero():
    """The whole point. Zero is a claim; absence is the truth."""
    unit_cost, total_cost = _resolve_costs(Decimal("200"), None, None)

    assert unit_cost is None
    assert total_cost is None


def test_total_follows_from_rate():
    unit_cost, total_cost = _resolve_costs(Decimal("200"), Decimal("312.50"), None)

    assert unit_cost == Decimal("312.50")
    assert total_cost == Decimal("62500.00")


def test_rate_follows_from_total():
    """Invoices often show only a line total after a discount."""
    unit_cost, total_cost = _resolve_costs(Decimal("15"), None, Decimal("12750"))

    assert unit_cost == Decimal("850.00")
    assert total_cost == Decimal("12750")


def test_an_explicit_total_is_never_overwritten_by_arithmetic():
    """Discounts, freight and rounding are real. 200 x 312.50 is 62500, but if
    the invoice says 61000 then the invoice is right and we are not."""
    unit_cost, total_cost = _resolve_costs(
        Decimal("200"), Decimal("312.50"), Decimal("61000")
    )

    assert unit_cost == Decimal("312.50")
    assert total_cost == Decimal("61000")


def test_rate_is_not_derived_when_quantity_is_zero():
    """Guards the division. A zero-quantity row is already invalid upstream,
    but this function must not be the thing that raises ZeroDivisionError."""
    unit_cost, total_cost = _resolve_costs(Decimal("0"), None, Decimal("500"))

    assert unit_cost is None
    assert total_cost == Decimal("500")


def test_derived_values_are_rounded_to_paise():
    unit_cost, total_cost = _resolve_costs(Decimal("3"), None, Decimal("100"))

    assert unit_cost == Decimal("33.33")
    assert total_cost == Decimal("100")


@pytest.mark.parametrize(
    ("quantity", "unit_cost", "total_cost", "expected_field"),
    [
        (Decimal("10"), Decimal("-1"), None, "unit_cost"),
        (Decimal("10"), None, Decimal("-5"), "total_cost"),
    ],
)
def test_negative_money_is_refused(quantity, unit_cost, total_cost, expected_field):
    """A negative price is never a discount -- it is a typo or a sign error, and
    letting it through would quietly reduce the company's recorded spend."""
    with pytest.raises(HTTPException) as exc:
        _resolve_costs(quantity, unit_cost, total_cost)

    assert exc.value.status_code == 422
    assert expected_field in exc.value.detail


def test_zero_is_accepted_when_it_is_actually_stated():
    """Distinct from "not recorded": a genuinely free delivery (a supplier
    replacing damaged goods) is a real, recordable fact."""
    unit_cost, total_cost = _resolve_costs(Decimal("10"), Decimal("0"), None)

    assert unit_cost == Decimal("0")
    assert total_cost == Decimal("0.00")
