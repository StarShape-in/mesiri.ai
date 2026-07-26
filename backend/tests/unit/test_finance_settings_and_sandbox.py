from __future__ import annotations

import pytest
from mesiri.domains.finance.router import (
    FinanceSettingsResponse,
    SandboxSimulateRequest,
    simulate_whatsapp_sandbox,
)


@pytest.mark.asyncio
async def test_simulate_whatsapp_sandbox_expense():
    req = SandboxSimulateRequest(message="Spent 45000 for excavator diesel at Indian Oil Bunk")
    auth_ctx = type("AuthCtx", (), {"organization_id": "00000000-0000-0000-0000-000000000001"})()
    res = await simulate_whatsapp_sandbox(req, auth_ctx)

    assert res.intent == "expense.create"
    assert "HIGH" in res.confidence
    assert res.fields["amount"] > 0
    assert "Dry-run preview" in res.reply_message


@pytest.mark.asyncio
async def test_simulate_whatsapp_sandbox_transfer():
    req = SandboxSimulateRequest(message="Transfer 15000 to site cash box")
    auth_ctx = type("AuthCtx", (), {"organization_id": "00000000-0000-0000-0000-000000000001"})()
    res = await simulate_whatsapp_sandbox(req, auth_ctx)

    assert res.intent == "finance.transfer"
    assert res.workflow_decision == "EXECUTE_TRANSFER"
    assert res.fields["amount"] > 0


def test_finance_settings_response_defaults():
    s = FinanceSettingsResponse()
    assert s.low_float_threshold == 50000
    assert s.low_balance_warning_enabled is True
    assert s.transfer_receipt_enabled is True
    assert s.expense_card_enabled is True
    assert s.weekly_digest_enabled is True
    assert s.weekly_digest_schedule == "weekly_monday"
