"""CorrectActivityQuantityCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from decimal import Decimal

from mesiri.domains.progress.validation import validate_correct_activity_quantity
from mesiri_contracts.application.commands.progress import CorrectActivityQuantityCommand

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PROGRESS_UPDATE_ID = "55555555-5555-4555-8555-555555555555"


def _command(**overrides) -> CorrectActivityQuantityCommand:
    base = dict(
        command_id="cmd_1",
        idempotency_key="idem_1",
        correlation_id="cor_1",
        organization_id=ORG,
        progress_update_id=PROGRESS_UPDATE_ID,
        new_quantity=Decimal("180"),
        new_unit="sqm",
        created_by=USR,
    )
    base.update(overrides)
    return CorrectActivityQuantityCommand(**base)


def test_valid_correction_has_no_reasons():
    assert validate_correct_activity_quantity(_command()) == []


def test_zero_quantity_is_rejected():
    reasons = validate_correct_activity_quantity(_command(new_quantity=Decimal("0")))
    assert "quantity must be positive" in reasons


def test_negative_quantity_is_rejected():
    reasons = validate_correct_activity_quantity(_command(new_quantity=Decimal("-5")))
    assert "quantity must be positive" in reasons


def test_missing_unit_is_rejected():
    reasons = validate_correct_activity_quantity(_command(new_unit=None))
    assert "unit is required" in reasons


def test_blank_unit_is_rejected():
    reasons = validate_correct_activity_quantity(_command(new_unit="   "))
    assert "unit is required" in reasons
