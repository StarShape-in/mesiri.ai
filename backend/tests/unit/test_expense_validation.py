"""RecordExpenseCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
CAT = "44444444-4444-4444-8444-444444444444"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> RecordExpenseCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        project_id=PRJ,
        category_id=CAT,
        amount=Decimal("100.00"),
        occurred_date=date.today(),
        created_by=USR,
    )
    base.update(overrides)
    return RecordExpenseCommand(**base)


def test_valid_command_has_no_reasons():
    assert validate(_command()) == []


def test_non_positive_amount_is_rejected():
    assert "amount must be greater than zero" in validate(_command(amount=Decimal("0")))
    assert "amount must be greater than zero" in validate(_command(amount=Decimal("-5")))


def test_blank_currency_is_rejected():
    assert "currency is required" in validate(_command(currency="  "))


def test_blank_category_is_rejected():
    assert "category_id or category_text is required" in validate(_command(category_id=" "))


def test_category_text_alone_satisfies_validation():
    reasons = validate(_command(category_id=None, category_text="materials"))
    assert "category_id or category_text is required" not in reasons


def test_missing_category_id_and_text_is_rejected():
    assert "category_id or category_text is required" in validate(
        _command(category_id=None, category_text=None)
    )
