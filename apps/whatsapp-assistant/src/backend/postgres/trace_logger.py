"""PostgreSQL implementation of runtime.logging_ports.TraceLogger.

Best-effort: swallows all exceptions and logs them. A trace failure must
never break the inbound pipeline.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

_log = logging.getLogger("mesiri.trace_logger")


def _build_engine():
    import os

    from sqlalchemy.ext.asyncio import create_async_engine

    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


class PostgresTraceLogger:
    """Writes journey_traces rows. Best-effort — never raises into the pipeline."""

    def __init__(self, engine=None) -> None:
        self._engine = engine

    def _get_engine(self):
        if self._engine is None:
            self._engine = _build_engine()
        return self._engine

    async def log_stage(
        self,
        *,
        correlation_id: str,
        stage: str,
        stage_payload: dict[str, Any] | None,
        duration_ms: int | None,
        succeeded: bool,
        error_code: str | None = None,
        error_message: str | None = None,
        severity: str = "info",
        event_source: str = "pipeline_stage",
    ) -> None:
        import json

        from sqlalchemy import text

        # A caller that doesn't say otherwise gets "info" on success and
        # "error" on failure; an explicit severity (e.g. "warning") always wins.
        resolved_severity = severity if severity != "info" or succeeded else "error"

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO journey_traces "
                        "(id, correlation_id, stage, stage_payload, duration_ms, "
                        "succeeded, error_code, error_message, severity, event_source) "
                        "VALUES (:id, :correlation_id, :stage, "
                        "CAST(:stage_payload AS jsonb), :duration_ms, :succeeded, "
                        ":error_code, :error_message, :severity, :event_source)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "correlation_id": correlation_id,
                        "stage": stage,
                        "stage_payload": (json.dumps(stage_payload) if stage_payload else None),
                        "duration_ms": duration_ms,
                        "succeeded": succeeded,
                        "error_code": error_code,
                        "error_message": error_message,
                        "severity": resolved_severity,
                        "event_source": event_source,
                    },
                )
        except Exception:  # noqa: BLE001
            _log.exception(
                "trace_logger.log_stage failed correlation_id=%s stage=%s", correlation_id, stage
            )

    async def log_provider_execution(
        self,
        *,
        correlation_id: str,
        stage: str,
        provider: str,
        operation: str,
        model: str | None,
        latency_ms: float | None,
        succeeded: bool,
        error_code: str | None = None,
    ) -> None:
        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO provider_executions "
                        "(id, correlation_id, stage, provider, operation, model, "
                        "latency_ms, succeeded, error_code) "
                        "VALUES (:id, :correlation_id, :stage, :provider, :operation, "
                        ":model, :latency_ms, :succeeded, :error_code)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "correlation_id": correlation_id,
                        "stage": stage,
                        "provider": provider,
                        "operation": operation,
                        "model": model,
                        "latency_ms": latency_ms,
                        "succeeded": succeeded,
                        "error_code": error_code,
                    },
                )
        except Exception:  # noqa: BLE001
            _log.exception(
                "trace_logger.log_provider_execution failed correlation_id=%s provider=%s",
                correlation_id,
                provider,
            )

    async def get_by_correlation_id(self, correlation_id: str) -> list[dict[str, Any]]:
        """Read path for the control-panel logs viewer's per-message trace
        drawer. `stage_payload` is deliberately excluded from the SELECT list
        (not just hidden client-side) — it can carry arbitrary AI/provider
        output and potentially sensitive context; provider/model attribution
        is exposed separately and safely via ``get_provider_executions``. A
        query failure here is NOT swallowed, unlike the write methods above."""
        from sqlalchemy import text

        async with self._get_engine().connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT stage, succeeded, duration_ms, error_code, error_message, "
                            "severity, event_source, created_at "
                            "FROM journey_traces WHERE correlation_id = :correlation_id "
                            "ORDER BY created_at ASC"
                        ),
                        {"correlation_id": correlation_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def get_stage_context(self, correlation_id: str) -> list[dict[str, Any]]:
        """Read path for the control-panel logs viewer's per-message "AI
        Context" panel -- the one place ``stage_payload`` is deliberately
        returned. Unlike ``get_by_correlation_id`` above, this is meant to
        expose the full understanding/resolved-context/canonical-event/
        planner payloads for debugging; callers MUST gate this behind
        platform-admin auth (see admin/logs_router.py), same trust boundary
        as the existing raw_payload/body_text detail route."""
        from sqlalchemy import text

        async with self._get_engine().connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT stage, stage_payload, succeeded, created_at "
                            "FROM journey_traces WHERE correlation_id = :correlation_id "
                            "ORDER BY created_at ASC"
                        ),
                        {"correlation_id": correlation_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def get_provider_executions(self, correlation_id: str) -> list[dict[str, Any]]:
        """Read path for the control-panel logs viewer's provider breakdown —
        the safe, structured answer to "which LLM/API handled this message",
        without ever needing to expose raw stage_payload contents."""
        from sqlalchemy import text

        async with self._get_engine().connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT stage, provider, operation, model, latency_ms, "
                            "succeeded, error_code, created_at "
                            "FROM provider_executions WHERE correlation_id = :correlation_id "
                            "ORDER BY created_at ASC"
                        ),
                        {"correlation_id": correlation_id},
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]
