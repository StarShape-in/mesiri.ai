"""Movement reason / direction combination rules — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

import pytest

from mesiri.domains.materials.validation import (
    RECEIPT_REASONS,
    USAGE_REASONS,
    is_valid_receipt_reason,
    is_valid_usage_reason,
    role_can_adjust,
)


@pytest.mark.parametrize("reason", RECEIPT_REASONS)
def test_valid_receipt_reasons_accepted(reason):
    assert is_valid_receipt_reason(reason) is True


@pytest.mark.parametrize("reason", USAGE_REASONS)
def test_valid_usage_reasons_accepted(reason):
    assert is_valid_usage_reason(reason) is True


def test_outflow_only_reason_rejected_for_receipt():
    assert is_valid_receipt_reason("CONSUMED") is False


def test_inflow_only_reason_rejected_for_usage():
    assert is_valid_usage_reason("RECEIVED") is False


def test_unknown_reason_rejected():
    assert is_valid_receipt_reason("NOT_A_REASON") is False
    assert is_valid_usage_reason("NOT_A_REASON") is False


@pytest.mark.parametrize("role", ["ADMIN", "admin", "PROJECT_MANAGER"])
def test_elevated_roles_can_adjust(role):
    assert role_can_adjust(role) is True


@pytest.mark.parametrize("role", ["SITE_ENGINEER", "FINANCE"])
def test_non_elevated_roles_cannot_adjust(role):
    assert role_can_adjust(role) is False
