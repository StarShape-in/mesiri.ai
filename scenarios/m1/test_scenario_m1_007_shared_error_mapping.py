"""scenario_m1_007_shared_error_mapping

Given  raw infrastructure exceptions (connection error, timeout)
When   they are mapped at the infrastructure boundary
Then   they become MesiriError values with the correct code, category,
       retryable flag, correlation id, and a redacted public form.

Expected Output          MesiriError with stable code + category
Expected Logs            n/a (pure mapping)
Expected Error Result    POSTGRES_UNAVAILABLE / OPERATION_TIMEOUT etc.
Forbidden Side Effects   raw exception types never cross the boundary
"""

import asyncio

import pytest

from mesiri.infrastructure.errors import (
    map_object_storage_error,
    map_postgres_error,
    map_redis_error,
)
from mesiri.observability import tracing
from mesiri_contracts.common.errors import ErrorCategory, MesiriError


@pytest.mark.scenario
def test_connection_errors_map_to_dependency_unavailable() -> None:
    pg = map_postgres_error(ConnectionError("refused"))
    assert isinstance(pg, MesiriError)
    assert pg.error_code == "POSTGRES_UNAVAILABLE"
    assert pg.category == ErrorCategory.DEPENDENCY
    assert pg.retryable is True

    assert map_redis_error(ConnectionError("x")).error_code == "REDIS_UNAVAILABLE"
    assert map_object_storage_error(OSError("x")).error_code == "OBJECT_STORAGE_UNAVAILABLE"


@pytest.mark.scenario
def test_timeouts_map_to_timeout_category() -> None:
    err = map_postgres_error(asyncio.TimeoutError())
    assert err.category == ErrorCategory.TIMEOUT
    assert err.error_code == "OPERATION_TIMEOUT"
    assert err.retryable is True


@pytest.mark.scenario
def test_mapping_captures_ambient_correlation_id() -> None:
    with tracing.correlation_scope(correlation_id="cor_map"):
        err = map_redis_error(ConnectionError("x"))
    assert err.correlation_id == "cor_map"


@pytest.mark.scenario
def test_public_form_is_redacted() -> None:
    err = map_postgres_error(ConnectionError("dsn=postgres://u:secretpw@h/db"))
    public = err.to_public_dict()
    assert "internal_message" not in public
    assert "secretpw" not in str(public)
