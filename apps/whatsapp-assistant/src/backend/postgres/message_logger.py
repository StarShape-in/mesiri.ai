"""PostgreSQL implementation of runtime.logging_ports.MessageLogger.

Best-effort: swallows all exceptions and logs them. A logging failure must
never break the inbound pipeline.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

_log = logging.getLogger("mesiri.message_logger")

_BODY_PREVIEW_LEN = 500


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


class PostgresMessageLogger:
    """Writes inbound_messages rows. Best-effort — never raises into the pipeline."""

    def __init__(self, engine=None) -> None:
        self._engine = engine

    def _get_engine(self):
        if self._engine is None:
            self._engine = _build_engine()
        return self._engine

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
    ) -> None:
        import json

        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO inbound_messages "
                        "(id, correlation_id, sender_wa_id, message_type, raw_payload, "
                        "normalized_message, body_text, media_object_key, dedup_key, "
                        "raw_payload_captured, retry_of_id) "
                        "VALUES (:id, :correlation_id, :sender_wa_id, :message_type, "
                        "CAST(:raw_payload AS jsonb), CAST(:normalized_message AS jsonb), "
                        ":body_text, :media_object_key, :dedup_key, "
                        ":raw_payload_captured, :retry_of_id) "
                        "ON CONFLICT (dedup_key) DO NOTHING"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "correlation_id": correlation_id,
                        "sender_wa_id": sender_wa_id,
                        "message_type": message_type,
                        "raw_payload": json.dumps(raw_payload),
                        "normalized_message": (
                            json.dumps(normalized_message) if normalized_message else None
                        ),
                        "body_text": body_text,
                        "media_object_key": media_object_key,
                        "dedup_key": dedup_key,
                        "raw_payload_captured": bool(raw_payload),
                        "retry_of_id": retry_of_id,
                    },
                )
        except Exception:  # noqa: BLE001
            _log.exception("message_logger.log_received failed correlation_id=%s", correlation_id)

    async def mark_completed(self, *, correlation_id: str) -> None:
        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE inbound_messages "
                        "SET processing_status = 'completed', processed_at = now() "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": correlation_id},
                )
        except Exception:  # noqa: BLE001
            _log.exception("message_logger.mark_completed failed correlation_id=%s", correlation_id)

    async def mark_failed(self, *, correlation_id: str, error_code: str) -> None:
        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE inbound_messages "
                        "SET processing_status = 'failed', processed_at = now(), "
                        "error_code = :error_code "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": correlation_id, "error_code": error_code},
                )
        except Exception:  # noqa: BLE001
            _log.exception("message_logger.mark_failed failed correlation_id=%s", correlation_id)

    async def list_recent(
        self,
        *,
        wa_id: str | None = None,
        status: str | None = None,
        provider: str | None = None,
        since_received_at: datetime | None = None,
        since_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Read path for the control-panel logs viewer.

        Two shapes: with no cursor, `limit`/`offset` history paging (newest
        first) alongside a `total` count. With `since_received_at`
        (+`since_id` as a tiebreaker), only messages strictly after that
        point, oldest first — a proper cursor for live polling that's immune
        to new inserts shifting an OFFSET out from under the caller (this
        mode ignores `offset`/`total` — it's a different, correct UX for
        tailing). `body_preview` is a short hint only; the full body is only
        ever returned by `get_message_detail`. Unlike the write methods
        above, a query failure here is NOT swallowed — the caller (an
        authenticated API endpoint) should see a real error.
        """
        from sqlalchemy import String, bindparam, text

        where = ["(:wa_id IS NULL OR sender_wa_id = :wa_id)", "(:status IS NULL OR processing_status = :status)"]
        params: dict[str, Any] = {"wa_id": wa_id, "status": status, "limit": limit}
        bind_types = [bindparam("wa_id", type_=String), bindparam("status", type_=String)]

        if provider is not None:
            where.append(
                "EXISTS (SELECT 1 FROM provider_executions pe "
                "WHERE pe.correlation_id = inbound_messages.correlation_id AND pe.provider = :provider)"
            )
            params["provider"] = provider
            bind_types.append(bindparam("provider", type_=String))

        is_live_cursor = since_received_at is not None
        if is_live_cursor:
            where.append(
                "(received_at > :since_received_at "
                "OR (received_at = :since_received_at AND id > :since_id))"
            )
            params["since_received_at"] = since_received_at
            params["since_id"] = uuid.UUID(since_id) if since_id else uuid.UUID(int=0)
            order_by = "received_at ASC, id ASC"
        else:
            order_by = "received_at DESC, id DESC"
            params["offset"] = offset

        query = (
            "SELECT id, correlation_id, sender_wa_id, message_type, "
            f"LEFT(COALESCE(body_text, ''), {_BODY_PREVIEW_LEN}) AS body_preview, "
            "processing_status, error_code, received_at, processed_at, "
            "acknowledged_at, acknowledged_by, raw_payload_captured, assistant_reply "
            "FROM inbound_messages "
            f"WHERE {' AND '.join(where)} "
            f"ORDER BY {order_by} "
            "LIMIT :limit" + ("" if is_live_cursor else " OFFSET :offset")
        )
        stmt = text(query).bindparams(*bind_types)

        async with self._get_engine().connect() as conn:
            rows = (await conn.execute(stmt, params)).mappings().all()
            total: int | None = None
            if not is_live_cursor:
                count_query = (
                    "SELECT COUNT(*) FROM inbound_messages "
                    f"WHERE {' AND '.join(where)}"
                )
                count_stmt = text(count_query).bindparams(*bind_types)
                count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
                total = (await conn.execute(count_stmt, count_params)).scalar_one()
        return [dict(row) for row in rows], total

    async def get_message_detail(self, message_id: str) -> dict[str, Any] | None:
        """Full record for the log detail view — the only place full
        `body_text` and `raw_payload` are ever returned."""
        from sqlalchemy import text

        async with self._get_engine().connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT id, correlation_id, sender_wa_id, message_type, "
                        "body_text, raw_payload, normalized_message, media_object_key, "
                        "processing_status, error_code, received_at, processed_at, "
                        "raw_payload_captured, acknowledged_at, acknowledged_by, retry_of_id, assistant_reply "
                        "FROM inbound_messages WHERE id = :id"
                    ),
                    {"id": uuid.UUID(message_id)},
                )
            ).mappings().first()
        return dict(row) if row is not None else None

    async def acknowledge(self, *, message_id: str, acknowledged_by: str) -> bool:
        """Mark a (typically failed) message as reviewed. Purely a triage
        marker — does not touch processing_status or re-run anything."""
        from sqlalchemy import text

        async with self._get_engine().begin() as conn:
            result = await conn.execute(
                text(
                    "UPDATE inbound_messages "
                    "SET acknowledged_at = now(), acknowledged_by = :acknowledged_by "
                    "WHERE id = :id"
                ),
                {"id": uuid.UUID(message_id), "acknowledged_by": acknowledged_by},
            )
        return result.rowcount > 0

    async def log_reply(self, *, correlation_id: str, reply: str) -> None:
        """UPDATE the row to add the assistant_reply."""
        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE inbound_messages "
                        "SET assistant_reply = :reply "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": correlation_id, "reply": reply},
                )
        except Exception:  # noqa: BLE001
            _log.exception("message_logger.log_reply failed correlation_id=%s", correlation_id)

    async def update_body_text(self, *, correlation_id: str, body_text: str) -> None:
        from sqlalchemy import text

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE inbound_messages SET body_text = :body_text "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": correlation_id, "body_text": body_text},
                )
        except Exception:  # noqa: BLE001
            _log.exception("message_logger.update_body_text failed correlation_id=%s", correlation_id)
