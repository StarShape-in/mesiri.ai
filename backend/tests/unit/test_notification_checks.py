"""application/notifications/checks.py -- pure timing decisions (#9 Notifications).

No I/O, no DB. The at-most-once guarantee itself is schema-enforced (see
that module's docstring) and has nothing to unit test here; these three
functions are what's worth pinning, since getting any of them wrong wakes
someone up at the wrong hour or silently drops a message outside the
WhatsApp session window.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from mesiri.application.notifications.checks import (
    is_after_cutoff,
    is_quiet_hours,
    is_within_whatsapp_session_window,
    next_sendable_time,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, 27, hour, minute)


# --- is_after_cutoff --------------------------------------------------------


def test_before_cutoff_is_false():
    assert is_after_cutoff(local_now=_dt(17, 59), cutoff=time(18, 0)) is False


def test_exactly_at_cutoff_is_true():
    assert is_after_cutoff(local_now=_dt(18, 0), cutoff=time(18, 0)) is True


def test_well_after_cutoff_is_true():
    assert is_after_cutoff(local_now=_dt(22, 0), cutoff=time(18, 0)) is True


# --- is_quiet_hours (overnight wraparound is the whole point) -------------


def test_quiet_hours_overnight_window_at_night():
    # 21:00 -> 07:00 window, checking 23:00 -- squarely inside.
    assert is_quiet_hours(local_now=_dt(23, 0), start=time(21, 0), end=time(7, 0)) is True


def test_quiet_hours_overnight_window_before_midnight_boundary():
    assert is_quiet_hours(local_now=_dt(21, 0), start=time(21, 0), end=time(7, 0)) is True


def test_quiet_hours_overnight_window_early_morning_tail():
    # 03:00 is still within the overnight span.
    assert is_quiet_hours(local_now=_dt(3, 0), start=time(21, 0), end=time(7, 0)) is True


def test_quiet_hours_overnight_window_exactly_at_end_is_not_quiet():
    assert is_quiet_hours(local_now=_dt(7, 0), start=time(21, 0), end=time(7, 0)) is False


def test_quiet_hours_daytime_is_not_quiet():
    assert is_quiet_hours(local_now=_dt(14, 0), start=time(21, 0), end=time(7, 0)) is False


def test_quiet_hours_same_day_window_not_overnight():
    # A hypothetical non-wrapping window (start < end) -- the simple branch.
    assert is_quiet_hours(local_now=_dt(13, 0), start=time(12, 0), end=time(14, 0)) is True
    assert is_quiet_hours(local_now=_dt(15, 0), start=time(12, 0), end=time(14, 0)) is False


# --- next_sendable_time -----------------------------------------------------


def test_next_sendable_time_outside_quiet_hours_is_unchanged():
    now = _dt(14, 0)
    assert next_sendable_time(local_now=now, quiet_start=time(21, 0), quiet_end=time(7, 0)) == now


def test_next_sendable_time_evening_head_defers_to_tomorrow_morning():
    now = _dt(22, 0)
    result = next_sendable_time(local_now=now, quiet_start=time(21, 0), quiet_end=time(7, 0))
    assert result.date() == now.date() + timedelta(days=1)
    assert result.time() == time(7, 0)


def test_next_sendable_time_early_morning_tail_defers_to_later_today():
    now = _dt(3, 0)
    result = next_sendable_time(local_now=now, quiet_start=time(21, 0), quiet_end=time(7, 0))
    assert result.date() == now.date()
    assert result.time() == time(7, 0)


# --- is_within_whatsapp_session_window --------------------------------------


def test_within_window_when_recent():
    now = _dt(12, 0)
    last_inbound = now - timedelta(hours=2)
    assert is_within_whatsapp_session_window(last_inbound_at=last_inbound, now=now) is True


def test_outside_window_when_over_24h():
    now = _dt(12, 0)
    last_inbound = now - timedelta(hours=25)
    assert is_within_whatsapp_session_window(last_inbound_at=last_inbound, now=now) is False


def test_exactly_24h_is_outside_the_window():
    now = _dt(12, 0)
    last_inbound = now - timedelta(hours=24)
    assert is_within_whatsapp_session_window(last_inbound_at=last_inbound, now=now) is False


def test_no_inbound_message_ever_fails_closed():
    assert is_within_whatsapp_session_window(last_inbound_at=None, now=_dt(12, 0)) is False
