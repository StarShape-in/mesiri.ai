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
    ) -> None:
        import json

        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO journey_traces "
                        "(id, correlation_id, stage, stage_payload, duration_ms, "
                        "succeeded, error_code, error_message) "
                        "VALUES (:id, :correlation_id, :stage, "
                        "CAST(:stage_payload AS jsonb), :duration_ms, :succeeded, "
                        ":error_code, :error_message)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "correlation_id": correlation_id,
                        "stage": stage,
                        "stage_payload": (
                            json.dumps(stage_payload) if stage_payload else None
                        ),
                        "duration_ms": duration_ms,
                        "succeeded": succeeded,
                        "error_code": error_code,
                        "error_message": error_message,
                    },
                )
        except Exception:  # noqa: BLE001
            _log.exception("trace_logger.log_stage failed correlation_id=%s stage=%s", correlation_id, stage)
