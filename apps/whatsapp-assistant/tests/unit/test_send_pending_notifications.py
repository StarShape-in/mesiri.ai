"""runtime/send_pending_notifications.py -- the pure rule_key -> message
mapping (#9 Notifications). Everything else in that module needs a live DB
and real WhatsApp credentials, so it is not covered here."""

from __future__ import annotations

from runtime.send_pending_notifications import _render


def test_stuck_confirmation_has_a_specific_message():
    text = _render("stuck_confirmation")
    assert "waiting" in text.lower() or "yes" in text.lower()


def test_unknown_rule_key_falls_back_to_a_generic_message():
    text = _render("some_future_rule_key")
    assert "pending item" in text.lower()
