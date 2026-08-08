"""Live infrastructure integration tests (M1).

Skipped by default (marker ``integration``). Run against the docker stack:

    make dev && make migrate && uv run pytest -m integration

They exercise the *real* Postgres and Redis adapters (object storage stays on
the fake unless R2 is configured), proving the same interfaces work against live
dependencies — not just fakes.
"""

from __future__ import annotations

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle
from mesiri.bootstrap.settings import Settings
from mesiri_contracts.common.health import DependencyState

pytestmark = pytest.mark.integration


@pytest.fixture
async def live_lifecycle():
    lc = AppLifecycle.create(Settings(), use_fakes=False)
    await lc.startup()
    yield lc
    await lc.shutdown()


async def test_live_readiness_is_healthy(live_lifecycle: AppLifecycle) -> None:
    report = await live_lifecycle.container.health_checker().readiness()
    assert report.state == DependencyState.HEALTHY, report.model_dump()


async def test_live_postgres_heartbeat_round_trip(live_lifecycle: AppLifecycle) -> None:
    pg = live_lifecycle.container.postgres
    await pg.write_heartbeat("integration-test", "alive")  # type: ignore[union-attr]
    row = await pg.read_heartbeat("integration-test")  # type: ignore[union-attr]
    assert row is not None and row["note"] == "alive"


async def test_live_redis_round_trip(live_lifecycle: AppLifecycle) -> None:
    redis = live_lifecycle.container.redis
    await redis.set_json("integration-test", {"ok": 1}, ttl_seconds=30)  # type: ignore[union-attr]
    assert await redis.get_json("integration-test") == {"ok": 1}  # type: ignore[union-attr]
