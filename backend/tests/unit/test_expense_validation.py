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


def test_missing_category_id_and_text_has_no_reasons():
    """category is optional at the pure-validation layer -- REST enforces
    category_id via its own request schema, and the WhatsApp/CQRS resolver
    falls back to a default category rather than rejecting (see
    resolution.py's PostgresExpenseCategoryResolver.get_or_create_default)."""
    assert validate(_command(category_id=None, category_text=None)) == []


def test_account_id_alone_has_no_reasons():
    assert validate(_command(account_id="55555555-5555-4555-8555-555555555555")) == []


def test_own_pocket_alone_has_no_reasons():
    assert validate(_command(paid_from_own_pocket=True)) == []


def test_account_id_and_own_pocket_together_is_rejected():
    reasons = validate(
        _command(account_id="55555555-5555-4555-8555-555555555555", paid_from_own_pocket=True)
    )
    assert "cannot select an account and 'paid from own pocket' at the same time" in reasons
