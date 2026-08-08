"""Shared helpers for M1 infrastructure scenarios.

All scenarios run against the in-process fakes so they need no docker or
credentials (see scenario m1_010). A live-stack variant is exercised by the
integration-marked tests in ``backend/tests/integration``.
"""

from __future__ import annotations

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle
from mesiri.bootstrap.settings import Settings


@pytest.fixture
def fake_lifecycle() -> AppLifecycle:
    return AppLifecycle.create(Settings(), use_fakes=True)
