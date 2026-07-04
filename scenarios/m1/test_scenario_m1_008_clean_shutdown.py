"""scenario_m1_008_clean_shutdown

Given  a started runtime
When   the runtime shuts down
Then   every dependency is disconnected, the runtime reports not-started, and a
       failing close on one dependency does not prevent the others from closing.

Expected Output          started is False; all disconnects attempted
Expected Logs            lifecycle.shutdown.begin ... complete
Expected Error Result    close failures are logged, not raised
Forbidden Side Effects   shutdown never raises
"""

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle


@pytest.mark.scenario
async def test_clean_shutdown(fake_lifecycle: AppLifecycle) -> None:
    await fake_lifecycle.startup()
    await fake_lifecycle.shutdown()
    assert fake_lifecycle.started is False
    # Fakes track their own connection state.
    assert fake_lifecycle.container.postgres._connected is False  # type: ignore[union-attr]
    assert fake_lifecycle.container.redis._connected is False  # type: ignore[union-attr]


@pytest.mark.scenario
async def test_shutdown_survives_a_failing_close(fake_lifecycle: AppLifecycle) -> None:
    await fake_lifecycle.startup()

    async def boom() -> None:
        raise RuntimeError("redis close failed")

    fake_lifecycle.container.redis.disconnect = boom  # type: ignore[assignment]

    # Must not raise even though one close fails.
    await fake_lifecycle.shutdown()
    assert fake_lifecycle.started is False
    assert fake_lifecycle.container.postgres._connected is False  # type: ignore[union-attr]
