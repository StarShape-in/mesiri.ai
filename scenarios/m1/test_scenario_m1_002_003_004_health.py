"""scenario_m1_002_postgres_health / 003_redis_health / 004_object_storage_health

Given  a started runtime with all dependencies reachable
When   readiness is evaluated
Then   each dependency reports HEALTHY with a measured latency.

Expected Output          DependencyStatus(state=HEALTHY, latency_ms>=0) per dep
Expected Logs            readiness probe results
Expected Error Result    none
Forbidden Side Effects   probes are read-only; no data mutated
"""

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle
from mesiri_contracts.common.health import DependencyState


@pytest.mark.scenario
@pytest.mark.parametrize("dependency", ["postgres", "redis", "object_storage"])
async def test_dependency_reports_healthy(fake_lifecycle: AppLifecycle, dependency: str) -> None:
    await fake_lifecycle.startup()
    try:
        report = await fake_lifecycle.container.health_checker().readiness()
        statuses = {d.name: d for d in report.dependencies}
        assert dependency in statuses, f"{dependency} not probed"
        dep = statuses[dependency]
        assert dep.state == DependencyState.HEALTHY
        assert dep.latency_ms is not None and dep.latency_ms >= 0
        assert dep.error_code is None
    finally:
        await fake_lifecycle.shutdown()
