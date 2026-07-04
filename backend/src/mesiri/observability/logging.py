"""Structured application logging (M1).

Emits one JSON object per log entry with a stable field set. Correlation ids are
pulled automatically from the ambient context (see ``tracing``), so callers only
pass event-specific fields.

Redaction is enforced at the boundary: any field whose key looks sensitive is
replaced with ``"***"``, and byte payloads are never serialized (only their
length). This is the single place that decides what is safe to log — never log
api keys, authorization headers, passwords, DSNs, or raw media.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from mesiri_contracts.common.errors import MesiriError

from ..bootstrap.settings import LogFormat, Settings
from . import tracing

# Substrings that mark a field as sensitive (case-insensitive).
_SENSITIVE_KEYS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "access_key",
    "credential",
    "dsn",
)

_REDACTED = "***"

# Stable ordering / allow-list of correlation + standard fields.
_STANDARD_FIELDS = (
    "correlation_id",
    "request_id",
    "message_id",
    "workflow_instance_id",
    "duration_ms",
    "error_code",
)


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(s in lowered for s in _SENSITIVE_KEYS):
        return _REDACTED
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v, key) for v in value]
    return value


class _JsonFormatter(logging.Formatter):
    def __init__(self, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "environment": self._environment,
            "event": record.getMessage(),
        }
        fields: dict[str, Any] = getattr(record, "mesiri_fields", {}) or {}
        # Correlation context first, then explicit fields (explicit wins).
        merged = {**tracing.current_context(), **fields}
        for key, val in merged.items():
            if val is None:
                continue
            payload[key] = _redact(val, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {**tracing.current_context(), **(getattr(record, "mesiri_fields", {}) or {})}
        cid = fields.get("correlation_id", "-")
        extras = " ".join(
            f"{k}={_redact(v, k)}" for k, v in fields.items() if k not in _STANDARD_FIELDS and v is not None
        )
        base = f"{record.levelname:<7} [{cid}] {record.getMessage()}"
        return f"{base} {extras}".rstrip()


class StructuredLogger:
    """Thin wrapper that merges correlation context and redacts fields."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _emit(self, level: int, event: str, error: MesiriError | None, fields: dict[str, Any]) -> None:
        clean = {k: v for k, v in fields.items() if v is not None}
        if error is not None:
            clean.setdefault("error_code", error.error_code)
            clean.setdefault("error_category", error.category.value)
            clean.setdefault("retryable", error.retryable)
            # internal_message is developer-facing and allowed in logs.
            clean.setdefault("internal_message", error.internal_message)
        self._logger.log(level, event, extra={"mesiri_fields": clean})

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, None, fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, None, fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, None, fields)

    def error(self, event: str, *, error: MesiriError | None = None, **fields: Any) -> None:
        self._emit(logging.ERROR, event, error, fields)


def configure_logging(settings: Settings) -> None:
    """Install the structured handler on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(settings.log.level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log.format is LogFormat.JSON:
        handler.setFormatter(_JsonFormatter(settings.service_name, settings.environment.value))
    else:
        handler.setFormatter(_ConsoleFormatter())
    root.addHandler(handler)


def get_logger(name: str = "mesiri") -> StructuredLogger:
    return StructuredLogger(logging.getLogger(name))


@contextmanager
def log_duration(logger: StructuredLogger, event: str, **fields: Any) -> Iterator[None]:
    """Log ``event`` on exit with ``duration_ms`` measured over the block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(event, duration_ms=duration_ms, **fields)
