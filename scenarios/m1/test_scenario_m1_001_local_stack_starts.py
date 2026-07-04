"""scenario_m1_001_local_stack_starts

Given  a valid local configuration
When   the runtime starts up
Then   configuration validates, every dependency connects, and the runtime
       reports itself started.

Expected Output          lifecycle.started is True after startup
Expected Logs            lifecycle.startup.begin ... lifecycle.startup.complete
Expected Error Result    none
Forbidden Side Effects   no domain records written; no external network calls
"""

import pytest

from mesiri.bootstrap.lifecycle import AppLifecycle


@pytest.mark.scenario
async def test_local_stack_starts(fake_lifecycle: AppLifecycle) -> None:
    assert fake_lifecycle.started is False
    await fake_lifecycle.startup()
    try:
        assert fake_lifecycle.started is True
    finally:
        await fake_lifecycle.shutdown()
