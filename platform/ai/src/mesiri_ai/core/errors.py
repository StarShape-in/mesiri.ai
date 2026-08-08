"""Provider error mapping (M3).

Converts provider SDK exceptions into the shared :class:`MesiriError` contract
inside the adapter, so no provider-specific exception crosses the AI provider
boundary. Malformed provider output is distinguished from transport failures
because callers treat them differently (retry vs. reject).
"""

from __future__ import annotations

from mesiri_contracts.common.errors import ErrorCategory, ErrorCode, MesiriError


def _is_timeout(exc: BaseException) -> bool:
    import asyncio

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    return "timeout" in type(exc).__name__.lower()


def map_provider_error(
    provider: str,
    exc: BaseException,
    *,
    correlation_id: str | None = None,
) -> MesiriError:
    if isinstance(exc, MesiriError):
        return exc.with_correlation(correlation_id)
    if _is_timeout(exc):
        return MesiriError(
            error_code=ErrorCode.PROVIDER_TIMEOUT.value,
            category=ErrorCategory.TIMEOUT,
            retryable=True,
            user_safe_message="The AI service took too long. Please try again.",
            internal_message=f"{provider} timeout: {type(exc).__name__}",
            correlation_id=correlation_id,
            details={"provider": provider},
        )
    return MesiriError(
        error_code=ErrorCode.PROVIDER_ERROR.value,
        category=ErrorCategory.PROVIDER,
        retryable=True,
        user_safe_message="The AI service is temporarily unavailable.",
        internal_message=f"{provider} error: {type(exc).__name__}: {exc}",
        correlation_id=correlation_id,
        details={"provider": provider},
    )


def provider_unavailable(
    provider: str, reason: str, *, correlation_id: str | None = None
) -> MesiriError:
    return MesiriError(
        error_code=ErrorCode.PROVIDER_UNAVAILABLE.value,
        category=ErrorCategory.PROVIDER,
        retryable=True,
        user_safe_message="The AI service is temporarily unavailable.",
        internal_message=f"{provider} unavailable: {reason}",
        correlation_id=correlation_id,
        details={"provider": provider},
    )


def malformed_output(
    provider: str, reason: str, *, correlation_id: str | None = None
) -> MesiriError:
    return MesiriError(
        error_code=ErrorCode.PROVIDER_MALFORMED_OUTPUT.value,
        category=ErrorCategory.SERIALIZATION,
        retryable=False,
        user_safe_message="The AI service returned an unexpected response.",
        internal_message=f"{provider} malformed output: {reason}",
        correlation_id=correlation_id,
        details={"provider": provider},
    )
