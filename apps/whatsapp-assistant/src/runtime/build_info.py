"""Which commit is running, and which media storage it is using.

Added because a whole class of "the fix didn't work" turned out to be
unanswerable: with a deploy failing at the SSH step, ten pushed fixes and a
green test suite say nothing about what the VPS is serving, and there was no
way to tell from the outside. Nobody should have to infer that from
behaviour again.

Resolution order, first hit wins:

1. ``MESIRI_BUILD_SHA`` -- set it in the unit file or the deploy script if
   the checkout ever stops being a git repo (a container image, say).
2. ``git rev-parse`` against this file's own repository. The VPS deploy is a
   ``git pull`` into /opt/mesiri, so this is accurate there today and needs
   no deploy change to start working -- which matters, since the deploy is
   the thing that is broken.
3. ``"unknown"`` -- never raises. A health probe must not fail because the
   build label could not be resolved.

Read once at import: the answer cannot change while the process lives.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

_UNKNOWN = "unknown"


@lru_cache(maxsize=1)
def build_sha() -> str:
    env = os.getenv("MESIRI_BUILD_SHA", "").strip()
    if env:
        return env
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell, no user input
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:  # noqa: BLE001 — a health probe never fails over a label
        return _UNKNOWN
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else _UNKNOWN


@lru_cache(maxsize=1)
def media_storage_provider() -> str:
    """Which object-storage adapter is live: "fake", "r2", or "unknown".

    Reported on /health for the same reason as the commit: with the fake
    adapter selected every photo is written to memory and every URL comes
    back as memory://, which the dashboard shows as "Photo unavailable". That
    reads as a broken feature and is a missing environment variable, and
    there was no way to tell the two apart from outside.

    The provider *name* only. A credential must never reach a public probe.
    Never raises -- a liveness check must not fail over a label.
    """
    try:
        from mesiri.bootstrap.settings import get_settings

        return str(get_settings().object_storage.provider.value)
    except Exception:  # noqa: BLE001 — a probe never fails over a label
        return _UNKNOWN
