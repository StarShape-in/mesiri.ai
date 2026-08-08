"""Provider resilience + error mapping (M3)."""

import asyncio

import pytest

from mesiri_ai.core.errors import malformed_output, map_provider_error, provider_unavailable
from mesiri_ai.core.fallback import call_with_resilience
from mesiri_contracts.common.errors import ErrorCategory, MesiriError


async def test_success_returns_result_and_latency():
    async def ok():
        return "value"

    result, latency_ms = await call_with_resilience(
        ok, provider="fake", operation="op", timeout_seconds=1.0, max_retries=0
    )
    assert result == "value"
    assert latency_ms >= 0


async def test_timeout_maps_to_provider_timeout():
    async def slow():
        await asyncio.sleep(0.2)

    with pytest.raises(MesiriError) as exc:
        await call_with_resilience(
            slow, provider="sarvam", operation="stt", timeout_seconds=0.01, max_retries=1
        )
    assert exc.value.error_code == "PROVIDER_TIMEOUT"
    assert exc.value.category == ErrorCategory.TIMEOUT


async def test_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ConnectionError("transient")
        return "ok"

    result, _ = await call_with_resilience(
        flaky,
        provider="fake",
        operation="op",
        timeout_seconds=1.0,
        max_retries=2,
        backoff_seconds=0.0,
    )
    assert result == "ok"
    assert attempts["n"] == 2


async def test_non_retryable_error_is_not_retried():
    attempts = {"n": 0}

    async def malformed():
        attempts["n"] += 1
        raise malformed_output("fake", "bad json")

    with pytest.raises(MesiriError) as exc:
        await call_with_resilience(
            malformed, provider="fake", operation="op", timeout_seconds=1.0, max_retries=3
        )
    assert exc.value.error_code == "PROVIDER_MALFORMED_OUTPUT"
    assert attempts["n"] == 1  # not retried


def test_error_mapping_preserves_correlation():
    err = map_provider_error("gemini", ConnectionError("x"), correlation_id="cor_1")
    assert err.error_code == "PROVIDER_ERROR"
    assert err.correlation_id == "cor_1"
    assert err.retryable is True


def test_unavailable_and_malformed_helpers():
    assert provider_unavailable("s", "down").error_code == "PROVIDER_UNAVAILABLE"
    assert malformed_output("g", "x").retryable is False
