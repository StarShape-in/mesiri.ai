"""scenario_m1_010_ci_without_external_credentials

Given  an environment with NO real credentials (no DB, no Redis, no R2, no AI keys)
When   the runtime starts and the golden scenario runs
Then   everything succeeds against the in-process fakes.

This is the guarantee that CI needs neither paid providers nor a live webhook.

Expected Output          golden scenario PASSED
Expected Logs            golden checklist all [ok]
Expected Error Result    none
Forbidden Side Effects   no network calls to any external provider
"""

import pytest

from mesiri.scripts.run_m1_golden_scenario import run


@pytest.mark.scenario
@pytest.mark.golden
async def test_golden_scenario_passes_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicitly strip anything that could point at real infrastructure.
    for var in (
        "MESIRI_POSTGRES__HOST",
        "MESIRI_REDIS__HOST",
        "MESIRI_OBJECT_STORAGE__PROVIDER",
        "MESIRI_SARVAM__API_KEY",
        "MESIRI_GEMINI__API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MESIRI_GOLDEN_USE_FAKES", "true")

    check = await run()
    failed = [label for label, ok, _ in check.items if not ok]
    assert check.passed, f"golden scenario failed steps: {failed}"
