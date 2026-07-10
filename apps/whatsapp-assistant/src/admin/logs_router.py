"""Read-only WhatsApp assistant log viewer for the control panel.

Platform-admin only (see mesiri.domains.shared.auth.require_platform_admin) --
this exposes real customer message content and phone numbers. Reads through
apps/whatsapp-assistant/src/backend/postgres/message_logger.py's list_recent
and trace_logger.py's get_by_correlation_id; this router adds no SQL of its
own, per the "one file owns a table's SQL" convention used throughout M8.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/logs", tags=["admin"])


class InboundMessageSummary(BaseModel):
    id: uuid.UUID
    correlation_id: str
    sender_wa_id: str
    message_type: str
    body_preview: str
    processing_status: str
    error_code: str | None = None
    received_at: datetime
    processed_at: datetime | None = None


class JourneyTraceEntry(BaseModel):
    stage: str
    succeeded: bool
    duration_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime


@router.get("/messages", response_model=list[InboundMessageSummary])
async def list_messages(
    request: Request,
    wa_id: str | None = None,
    status: str | None = None,
    since_received_at: datetime | None = None,
    since_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _admin: dict = Depends(require_platform_admin),
) -> list[InboundMessageSummary]:
    message_logger = request.app.state.container.message_logger
    rows = await message_logger.list_recent(
        wa_id=wa_id,
        status=status,
        since_received_at=since_received_at,
        since_id=since_id,
        limit=limit,
    )
    return [InboundMessageSummary(**row) for row in rows]


@router.get("/messages/{correlation_id}/trace", response_model=list[JourneyTraceEntry])
async def get_message_trace(
    request: Request,
    correlation_id: str,
    _admin: dict = Depends(require_platform_admin),
) -> list[JourneyTraceEntry]:
    trace_logger = request.app.state.container.trace_logger
    rows = await trace_logger.get_by_correlation_id(correlation_id)
    return [JourneyTraceEntry(**row) for row in rows]
