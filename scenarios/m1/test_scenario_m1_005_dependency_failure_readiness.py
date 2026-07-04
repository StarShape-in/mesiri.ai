"""scenario_m1_005_dependency_failure_readiness

Given  a runtime whose PostgreSQL dependency is unreachable
When   readiness is evaluated
Then   the aggregate report is UNHEALTHY, PostgreSQL reports UNHEALTHY with a
       structured error_code, and no raw exception leaks into the report.

Expected Output          report.state == UNHEALTHY; postgres.error_code set
Expected Logs            probe failure recorded
Expected Error Result    POSTGRES_UNAVAILABLE surfaced as user-safe detail only
Forbidden Side Effects   readiness never raises; no secrets in the report
"""

import json

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle
from mesiri_contracts.common.health import DependencyState


@pytest.mark.scenario
async def test_dependency_failure_makes_readiness_unhealthy(fake_lifecycle: AppLifecycle) -> None:
    await fake_lifecycle.startup()
    try:
        # Inject a failure into the fake PostgreSQL adapter.
        fake_lifecycle.container.postgres.fail_health = True  # type: ignore[union-attr]

        report = await fake_lifecycle.container.health_checker().readiness()
        assert report.state == DependencyState.UNHEALTHY

        pg = next(d for d in report.dependencies if d.name == "postgres")
        assert pg.state == DependencyState.UNHEALTHY
        assert pg.error_code == "POSTGRES_UNAVAILABLE"

        # No secrets / DSNs leak through the serialized report.
        serialized = json.dumps(report.model_dump())
        assert "mesiri_local_dev" not in serialized
        assert "password" not in serialized.lower()
    finally:
        await fake_lifecycle.shutdown()
