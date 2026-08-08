"""The running commit must be reportable, and must never break the probe.

Added after ten pushed fixes could not be distinguished from ten fixes that
never shipped, because a failing deploy and a working one produced the same
`{"status": "ok"}`.
"""

from __future__ import annotations

from runtime.build_info import _UNKNOWN, build_sha


def test_a_build_label_is_always_produced():
    build_sha.cache_clear()
    assert build_sha().strip()


def test_an_explicit_env_var_wins():
    """The escape hatch for a deploy where the checkout is not a git repo."""
    import os

    build_sha.cache_clear()
    os.environ["MESIRI_BUILD_SHA"] = "deadbeef"
    try:
        assert build_sha() == "deadbeef"
    finally:
        del os.environ["MESIRI_BUILD_SHA"]
        build_sha.cache_clear()


def test_it_degrades_instead_of_raising(monkeypatch):
    """A health probe must not fail because the label could not be resolved
    -- that would turn a cosmetic gap into an outage."""
    import subprocess

    monkeypatch.delenv("MESIRI_BUILD_SHA", raising=False)

    def _boom(*_args, **_kwargs):
        raise OSError("git not installed")

    monkeypatch.setattr(subprocess, "run", _boom)
    build_sha.cache_clear()
    try:
        assert build_sha() == _UNKNOWN
    finally:
        build_sha.cache_clear()


def test_the_media_storage_provider_is_reportable():
    """The symptom this answers: a photo attaches fine and then shows as
    "Photo unavailable" in the dashboard. That is the fake adapter handing
    back memory:// URLs -- a missing environment variable, not a broken
    feature -- and there was no way to tell the two apart from outside.

    Deliberately does NOT build the app. An earlier version did, and needed
    the WhatsApp credentials to construct Settings: it passed locally, where
    those are set, and failed in CI, where they are not. A health label
    should be testable without standing up the service it labels.
    """
    from runtime.build_info import media_storage_provider

    media_storage_provider.cache_clear()
    assert media_storage_provider() in {"fake", "r2", _UNKNOWN}


def test_the_provider_lookup_never_raises(monkeypatch):
    """A liveness probe must not fail because a label could not be resolved."""
    import mesiri.bootstrap.settings as settings_module

    def _boom():
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr(settings_module, "get_settings", _boom)
    from runtime.build_info import media_storage_provider

    media_storage_provider.cache_clear()
    try:
        assert media_storage_provider() == _UNKNOWN
    finally:
        media_storage_provider.cache_clear()


def test_the_provider_label_carries_no_credential():
    """Only the adapter name is ever exposed."""
    from runtime.build_info import media_storage_provider

    media_storage_provider.cache_clear()
    label = media_storage_provider().lower()

    assert "key" not in label
    assert "secret" not in label
    assert "http" not in label
