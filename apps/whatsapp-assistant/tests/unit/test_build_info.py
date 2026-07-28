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
