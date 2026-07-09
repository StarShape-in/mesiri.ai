"""Material domain validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mesiri.domains.materials.validation import validate, validate_receipt, validate_usage
from mesiri_contracts.application.commands.material import (
    RecordMaterialReceiptCommand,
    RecordMaterialUsageCommand,
)

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _receipt(**overrides) -> RecordMaterialReceiptCommand:
    base = dict(
        command_id="cmd_1",
        idempotency_key="wf_1",
        correlation_id="cor_1",
        organization_id=ORG,
        project_id=PRJ,
        site_id=None,
        material_name="cement",
        quantity=Decimal(20),
        unit="bags",
        occurred_date=date.today(),
        created_by=USR,
    )
    base.update(overrides)
    return RecordMaterialReceiptCommand(**base)


def _usage(**overrides) -> RecordMaterialUsageCommand:
    base = dict(
        command_id="cmd_1",
        idempotency_key="wf_1",
        correlation_id="cor_1",
        organization_id=ORG,
        project_id=PRJ,
        site_id=None,
        material_name="sand",
        quantity=Decimal(5),
        unit="tons",
        occurred_date=date.today(),
        created_by=USR,
    )
    base.update(overrides)
    return RecordMaterialUsageCommand(**base)


def test_valid_receipt_passes():
    assert validate_receipt(_receipt()) == []


def test_valid_usage_passes():
    assert validate_usage(_usage()) == []


def test_receipt_missing_project_id_rejected():
    reasons = validate_receipt(_receipt(project_id=None))
    assert "project is not resolved" in reasons


def test_usage_missing_project_id_rejected():
    reasons = validate_usage(_usage(project_id=None))
    assert "project is not resolved" in reasons


@pytest.mark.parametrize("quantity", [Decimal(0), Decimal(-1)])
def test_non_positive_quantity_rejected(quantity):
    assert "quantity must be positive" in validate_receipt(_receipt(quantity=quantity))


def test_empty_material_name_rejected():
    assert "material_name is required" in validate_receipt(_receipt(material_name="  "))


def test_empty_unit_rejected():
    assert "unit is required" in validate_receipt(_receipt(unit=""))


def test_multiple_violations_all_reported():
    reasons = validate_receipt(
        _receipt(project_id=None, quantity=Decimal(0), material_name="", unit="")
    )
    assert len(reasons) == 4


def test_validate_dispatches_by_command_type():
    assert validate(_receipt()) == []
    assert validate(_usage()) == []
    assert validate(_receipt(project_id=None)) == ["project is not resolved"]
