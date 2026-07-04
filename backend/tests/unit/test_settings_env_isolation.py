"""Regression: nested settings must not read unprefixed env vars.

Nested sections are plain BaseModel populated via MESIRI_*__* only. A bare
``USER`` env var (which exists as ``root`` on Linux) must NOT leak into
``postgres.user`` — that bug surfaced only on Linux during deployment.
"""

from __future__ import annotations

import pytest

from mesiri.bootstrap.settings import Settings


def test_bare_user_env_does_not_override_postgres_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER", "root")
    monkeypatch.setenv("PASSWORD", "should_not_be_used")
    monkeypatch.delenv("MESIRI_POSTGRES__USER", raising=False)
    s = Settings()
    assert s.postgres.user == "mesiri"
    assert s.postgres.password.get_secret_value() == "mesiri_local_dev"


def test_prefixed_nested_env_still_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MESIRI_POSTGRES__USER", "custom_user")
    s = Settings()
    assert s.postgres.user == "custom_user"
