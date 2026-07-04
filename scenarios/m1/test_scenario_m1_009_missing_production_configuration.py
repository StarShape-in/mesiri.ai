"""scenario_m1_009_missing_production_configuration

Given  a production environment missing required secrets / using fakes
When   runtime configuration is validated
Then   validation fails fast with a CONFIG_MISSING error naming what is missing,
       before any dependency is contacted.

Expected Output          MesiriError(CONFIG_MISSING) raised at create()
Expected Logs            n/a (fails before logging emits work)
Expected Error Result    configuration category, non-retryable
Forbidden Side Effects   no adapters connected; local defaults are NOT accepted
"""

import pytest

from mesiri.bootstrap.settings import Settings
from mesiri_contracts.common.errors import ErrorCategory, MesiriError


@pytest.mark.scenario
def test_production_with_local_defaults_fails_fast() -> None:
    settings = Settings(environment="production")  # keeps local default password + fake storage
    with pytest.raises(MesiriError) as exc:
        settings.validate_runtime()
    err = exc.value
    assert err.error_code == "CONFIG_MISSING"
    assert err.category == ErrorCategory.CONFIGURATION
    assert err.retryable is False
    missing = err.details["missing"]
    assert any("PASSWORD" in m for m in missing)
    assert any("PROVIDER" in m for m in missing)


@pytest.mark.scenario
def test_local_environment_accepts_defaults() -> None:
    # Local development must remain frictionless.
    Settings(environment="local").validate_runtime()  # does not raise
