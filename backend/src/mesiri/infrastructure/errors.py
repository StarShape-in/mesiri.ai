"""Infrastructure error mapping (M1).

Converts raw driver/SDK exceptions into the shared :class:`MesiriError`
contract *inside* the adapter, so no provider-specific exception ever crosses
the infrastructure boundary. Timeouts are detected and classified distinctly
from generic unavailability because callers retry them differently.
"""

from __future__ import annotations

import asyncio

from mesiri_contracts.common.errors import ErrorCode, MesiriError

from ..observability import tracing


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name


def map_postgres_error(exc: BaseException) -> MesiriError:
    correlation_id = tracing.get_correlation_id()
    if _is_timeout(exc):
        return MesiriError.timeout(
            "postgres operation",
            code=ErrorCode.OPERATION_TIMEOUT.value,
            correlation_id=correlation_id,
            details={"cause": type(exc).__name__},
        )
    return MesiriError.dependency_unavailable(
        "postgres",
        code=ErrorCode.POSTGRES_UNAVAILABLE.value,
        internal_message=f"postgres error: {type(exc).__name__}: {exc}",
        correlation_id=correlation_id,
    )


def map_redis_error(exc: BaseException) -> MesiriError:
    correlation_id = tracing.get_correlation_id()
    if _is_timeout(exc):
        return MesiriError.timeout(
            "redis operation",
            code=ErrorCode.OPERATION_TIMEOUT.value,
            correlation_id=correlation_id,
            details={"cause": type(exc).__name__},
        )
    return MesiriError.dependency_unavailable(
        "redis",
        code=ErrorCode.REDIS_UNAVAILABLE.value,
        internal_message=f"redis error: {type(exc).__name__}: {exc}",
        correlation_id=correlation_id,
    )


def map_object_storage_error(exc: BaseException) -> MesiriError:
    correlation_id = tracing.get_correlation_id()
    if _is_timeout(exc):
        return MesiriError.timeout(
            "object storage operation",
            code=ErrorCode.OPERATION_TIMEOUT.value,
            correlation_id=correlation_id,
            details={"cause": type(exc).__name__},
        )
    return MesiriError.dependency_unavailable(
        "object_storage",
        code=ErrorCode.OBJECT_STORAGE_UNAVAILABLE.value,
        internal_message=f"object storage error: {type(exc).__name__}: {exc}",
        correlation_id=correlation_id,
    )
