"""CreateAutomationCommand structural validation — pure function, no DB."""

from __future__ import annotations

from mesiri.application.automations.create_commands import CreateAutomationCommand
from mesiri.application.automations.create_validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
SITE = "44444444-4444-4444-8444-444444444444"


def _command(**overrides) -> CreateAutomationCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        action="REMINDER",
        audience="SELF",
        message="please submit your DPR",
        time_of_day="17:00",
    )
    base.update(overrides)
    return CreateAutomationCommand(**base)


def test_valid_self_reminder_passes():
    assert validate(_command()) == []


def test_self_digest_needs_no_special_role():
    cmd = _command(created_by_role="SITE_ENGINEER", audience="SELF")
    assert validate(cmd) == []


def test_targeting_others_requires_admin_or_pm():
    cmd = _command(created_by_role="SITE_ENGINEER", audience="ROLE", audience_role="SITE_ENGINEER")
    reasons = validate(cmd)
    assert "only an admin or project manager can target an automation at other people" in reasons


def test_admin_may_target_a_role():
    cmd = _command(created_by_role="ADMIN", audience="ROLE", audience_role="SITE_ENGINEER")
    assert validate(cmd) == []


def test_users_audience_needs_ids_or_names():
    cmd = _command(created_by_role="ADMIN", audience="USERS")
    reasons = validate(cmd)
    assert "audience_user_ids or audience_names is required when audience is USERS" in reasons


def test_role_audience_needs_a_role():
    cmd = _command(created_by_role="ADMIN", audience="ROLE")
    reasons = validate(cmd)
    assert "audience_role is required when audience is ROLE" in reasons


def test_reminder_needs_a_message():
    cmd = _command(action="REMINDER", message="  ")
    reasons = validate(cmd)
    assert "message is required when action is REMINDER" in reasons


def test_send_dpr_needs_a_site():
    cmd = _command(action="SEND_DPR", message=None, site_id=None)
    reasons = validate(cmd)
    assert "a site is required to send a DPR (a DPR is site-scoped)" in reasons


def test_send_dpr_with_site_passes():
    cmd = _command(action="SEND_DPR", message=None, site_id=SITE)
    assert validate(cmd) == []


def test_weekly_needs_day_of_week():
    cmd = _command(frequency="WEEKLY", day_of_week=None)
    reasons = validate(cmd)
    assert "day_of_week is required when frequency is WEEKLY" in reasons


def test_day_of_week_out_of_range_is_rejected():
    cmd = _command(frequency="WEEKLY", day_of_week=9)
    reasons = validate(cmd)
    assert "day_of_week must be 0 (Monday) through 6 (Sunday)" in reasons


def test_malformed_time_of_day_is_rejected():
    cmd = _command(time_of_day="not-a-time")
    reasons = validate(cmd)
    assert 'time_of_day must be "HH:MM"' in reasons


def test_unrecognised_action_is_rejected():
    cmd = _command(action="DO_A_BARREL_ROLL", message=None)
    reasons = validate(cmd)
    assert any("not a recognised automation action" in r for r in reasons)
