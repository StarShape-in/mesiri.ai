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
        retry_of_id: str | None = None,
        organization_id: str | None = None,
    ) -> None:
        """INSERT the inbound message row at receipt time. Idempotent on dedup_key."""
        ...

    async def update_context(
        self,
        *,
        correlation_id: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        site_id: str | None = None,
    ) -> None:
        """UPDATE the row's organization, project, and site context."""
        ...

    async def mark_completed(self, *, correlation_id: str) -> None:
        """UPDATE the row to processing_status='completed' with processed_at=now()."""
        ...

    async def mark_failed(self, *, correlation_id: str, error_code: str) -> None:
        """UPDATE the row to processing_status='failed' with the error code."""
        ...

    async def log_reply(self, *, correlation_id: str, reply: str) -> None:
        """UPDATE the row to add the assistant_reply."""
        ...

    async def update_body_text(self, *, correlation_id: str, body_text: str) -> None:
        """UPDATE the row's body_text column (e.g. after speech transcription)."""
        ...

    async def link_workflow_instance(
        self, *, correlation_id: str, workflow_instance_id: str
    ) -> None:
        """UPDATE the row's workflow_instance_id -- called whenever this
        message started or resumed a workflow, so the logs viewer can group
        the multi-turn interaction (e.g. voice expense -> confirmation)."""
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
        severity: str = "info",
        event_source: str = "pipeline_stage",
    ) -> None:
        """INSERT a trace row for one pipeline stage (or, with a non-default
        ``event_source``, for an unhandled exception / admin action)."""
        ...

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
        """INSERT a row recording which LLM/provider handled one call."""
        ...
