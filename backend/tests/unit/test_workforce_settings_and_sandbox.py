from __future__ import annotations

import pytest

from mesiri.domains.workforce.router import (
    LabourSandboxSimulateRequest,
    LabourSettingsResponse,
    simulate_labour_sandbox,
)


def _fake_auth_ctx():
    return type("AuthCtx", (), {"organization_id": "00000000-0000-0000-0000-000000000001"})()


@pytest.mark.asyncio
async def test_simulate_labour_sandbox_headcount_group():
    req = LabourSandboxSimulateRequest(message="12 helpers and 3 masons worked today")
    res = await simulate_labour_sandbox(req, _fake_auth_ctx())

    assert res.intent == "labour.record_attendance"
    assert "HIGH" in res.confidence
    assert res.fields["total_headcount"] == 15
    assert "No DB row created" in res.reply_message
    assert len(res.line_summaries) == 2


@pytest.mark.asyncio
async def test_simulate_labour_sandbox_no_match_falls_back_to_single_worker():
    req = LabourSandboxSimulateRequest(message="attendance recorded for the site")
    res = await simulate_labour_sandbox(req, _fake_auth_ctx())

    assert res.fields["total_headcount"] == 1
    assert res.line_summaries


def test_labour_settings_response_defaults():
    s = LabourSettingsResponse()
    assert s.missing_report_reminder_enabled is True
    assert s.missing_report_reminder_time == "18:00"
    assert s.headcount_anomaly_alert_enabled is True
    assert s.wage_change_alert_enabled is True
    assert s.require_dashboard_approval_for_new_worker is False
