"""scenario_m1_006_correlation_across_dependencies

Given  a started runtime and a single minted correlation_id
When   a journey performs Postgres, Redis, and object-storage operations inside
       one correlation scope
Then   the same correlation_id is observed at every step (no per-layer id churn).

Expected Output          one correlation_id across all operations
Expected Logs            every log within the scope carries that correlation_id
Expected Error Result    none
Forbidden Side Effects   correlation ids are not regenerated downstream
"""

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle
from mesiri.observability import tracing
from mesiri_contracts.common.ids import new_correlation_id


@pytest.mark.scenario
async def test_correlation_preserved_across_dependencies(fake_lifecycle: AppLifecycle) -> None:
    await fake_lifecycle.startup()
    c = fake_lifecycle.container
    try:
        correlation_id = new_correlation_id()
        seen = set()
        with tracing.correlation_scope(correlation_id=correlation_id):
            seen.add(tracing.get_correlation_id())
            await c.postgres.write_heartbeat("s006", "x")  # type: ignore[union-attr]
            seen.add(tracing.get_correlation_id())
            await c.redis.set_json("s006", {"v": 1})  # type: ignore[union-attr]
            seen.add(tracing.get_correlation_id())
            await c.object_storage.put_object("s006", b"x")
            seen.add(tracing.get_correlation_id())

        assert seen == {correlation_id}
        # Scope cleanup: id is unbound after the block.
        assert tracing.get_correlation_id() is None
    finally:
        await fake_lifecycle.shutdown()


@pytest.mark.scenario
async def test_existing_correlation_not_overwritten() -> None:
    outer = new_correlation_id()
    with tracing.correlation_scope(correlation_id=outer):
        # A nested scope without an explicit id must inherit, not mint a new one.
        with tracing.correlation_scope():
            assert tracing.get_correlation_id() == outer
