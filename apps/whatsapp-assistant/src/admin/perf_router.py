"""Latency/performance viewer for the control panel (platform-admin only).

Read-only aggregates over journey_traces/provider_executions/inbound_messages
-- the same queries run by hand throughout the M9 latency investigation
(stage breakdown, provider-call breakdown, wall-clock by modality, worst
offenders, per-message prepipeline step ranking), made reusable instead of
re-typing SQL into a DB client every time. This router adds no SQL of its
own, per the "one file owns a table's SQL" convention used throughout M8/M9
-- reads go through trace_logger.py's get_stage_summary/get_provider_summary/
get_prepipeline_recent and message_logger.py's get_wall_time_summary/
get_worst_offenders.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/perf", tags=["admin"])


class StageSummaryEntry(BaseModel):
    stage: str
    n: int
    failures: int
    avg_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: int | None = None


class ProviderSummaryEntry(BaseModel):
    stage: str
    provider: str
    operation: str
    model: str | None = None
    n: int
    failures: int
    avg_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None


class WallTimeSummaryEntry(BaseModel):
    message_type: str
    n: int
    avg_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None


class WorstOffenderEntry(BaseModel):
    correlation_id: str
    message_type: str
    received_at: datetime
    processed_at: datetime | None = None
    wall_ms: float | None = None


class PrepipelineEntry(BaseModel):
    correlation_id: str
    stage_payload: dict | None = None
    duration_ms: int | None = None
    succeeded: bool
    created_at: datetime


class PerfSummary(BaseModel):
    since: datetime
    stages: list[StageSummaryEntry]
    providers: list[ProviderSummaryEntry]
    wall_times: list[WallTimeSummaryEntry]


def _since(since_minutes: int) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=since_minutes)


@router.get("/summary", response_model=PerfSummary)
async def get_perf_summary(
    request: Request,
    since_minutes: int = Query(default=120, ge=1, le=10080),
    _admin: dict = Depends(require_platform_admin),
) -> PerfSummary:
    trace_logger = request.app.state.container.trace_logger
    message_logger = request.app.state.container.message_logger
    since = _since(since_minutes)

    stages = await trace_logger.get_stage_summary(since)
    providers = await trace_logger.get_provider_summary(since)
    wall_times = await message_logger.get_wall_time_summary(since)

    return PerfSummary(
        since=since,
        stages=[StageSummaryEntry(**row) for row in stages],
        providers=[ProviderSummaryEntry(**row) for row in providers],
        wall_times=[WallTimeSummaryEntry(**row) for row in wall_times],
    )


@router.get("/worst", response_model=list[WorstOffenderEntry])
async def get_worst_offenders(
    request: Request,
    since_minutes: int = Query(default=120, ge=1, le=10080),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: dict = Depends(require_platform_admin),
) -> list[WorstOffenderEntry]:
    message_logger = request.app.state.container.message_logger
    rows = await message_logger.get_worst_offenders(_since(since_minutes), limit)
    return [WorstOffenderEntry(**row) for row in rows]


@router.get("/prepipeline", response_model=list[PrepipelineEntry])
async def get_prepipeline_breakdown(
    request: Request,
    since_minutes: int = Query(default=120, ge=1, le=10080),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: dict = Depends(require_platform_admin),
) -> list[PrepipelineEntry]:
    trace_logger = request.app.state.container.trace_logger
    rows = await trace_logger.get_prepipeline_recent(_since(since_minutes), limit)
    return [PrepipelineEntry(**row) for row in rows]
