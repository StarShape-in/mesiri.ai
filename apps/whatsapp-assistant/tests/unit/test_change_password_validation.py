"""ChangePassword schema — pure validation, no DB, no HTTP server."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from auth.router import ChangePassword


def test_change_password_accepts_valid_input():
    body = ChangePassword(current_password="old-password", new_password="new-password-123")
    assert body.new_password == "new-password-123"


def test_change_password_rejects_short_new_password():
    with pytest.raises(ValidationError):
        ChangePassword(current_password="old-password", new_password="short")
