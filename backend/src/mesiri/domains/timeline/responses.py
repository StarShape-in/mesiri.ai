from __future__ import annotations

import datetime
import uuid
from typing import Any

from pydantic import BaseModel


class TimelineEntryResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    site_id: uuid.UUID | None
    event_type: str
    summary: str
    payload: dict[str, Any]
    occurred_at: datetime.datetime
    correlation_id: str | None
    source_aggregate_type: str
    source_aggregate_id: uuid.UUID
    created_at: datetime.datetime


class TimelineEntriesListResponse(BaseModel):
    items: list[TimelineEntryResponse]
    total: int


class TimelineDaySummaryItem(BaseModel):
    day: datetime.date
    event_type: str
    count: int


class TimelineDaySummaryResponse(BaseModel):
    items: list[TimelineDaySummaryItem]
