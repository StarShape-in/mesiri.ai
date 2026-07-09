"""Ports for best-effort message and trace logging.

These are debug/observability ports — not domain ports. Implementations must
never raise into the pipeline; a logging failure is swallowed and logged.

- ``MessageLogger`` captures the raw inbound message and its processing status.
- ``TraceLogger`` captures one row per pipeline stage with its v2 contract payload.
"""

from __future__ import annotations

from typing import Any, Protocol


class MessageLogger(Protocol):
    """Best-effort log of every inbound message for debugging and replay."""

    async def log_received(
        self,
        *,
        correlation_id: str,
        sender_wa_id: str,
        message_type: str,
        raw_payload: dict[str, Any],
        normalized_message: dict[str, Any] | None,
        body_text: str | None,
        media_object_key: str | None,
        dedup_key: str,
    ) -> None:
        """INSERT the inbound message row at receipt time. Idempotent on dedup_key."""
        ...

    async def mark_completed(self, *, correlation_id: str) -> None:
        """UPDATE the row to processing_status='completed' with processed_at=now()."""
        ...

    async def mark_failed(self, *, correlation_id: str, error_code: str) -> None:
        """UPDATE the row to processing_status='failed' with the error code."""
        ...


class TraceLogger(Protocol):
    """Best-effort per-stage pipeline trace."""

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
        """INSERT a trace row for one pipeline stage."""
        ...
