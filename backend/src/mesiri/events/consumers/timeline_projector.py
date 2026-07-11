"""Projects confirmed outbox_events into timeline_entries (the Timeline read model).

Per architecture: downstream systems (dashboard/timeline UI) read only
timeline_entries, never business tables. This module is the single writer
of that projection — a plain idempotent batch function, not a persistent
worker (see mesiri.application.materials.recovery for the same convention:
"invocable manually or via a cron entry — not a background worker service").

Concurrency safety: uses `SELECT ... FOR UPDATE SKIP LOCKED` on the
outbox_events batch select. Two concurrent invocations (e.g. overlapping
cron runs) each lock a disjoint set of unpublished rows and skip rows the
other already holds, rather than blocking or double-projecting. This is
preferred over an ON-CONFLICT claim table (as used by
material_execution.py's idempotency_keys) because here the "claim" and the
"do the work" are the same short transaction, not a claim-now /
complete-later split — SKIP LOCKED is the standard Postgres primitive for
exactly this "queue drain" shape, and outbox_events' own
ix_outbox_events_unpublished partial index was built for it.

Crash safety: published_at is only set after the timeline_entries insert
succeeds, in the same transaction. If the process dies mid-batch, the
transaction rolls back entirely — no row is left half-projected, and
everything in that batch is retried (safely, since it was never marked
published) on the next invocation.
"""

from __future__ import annotations

import datetime
import json
import uuid
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

_outbox_events = sa.Table(
    "outbox_events",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("aggregate_type", sa.String),
    sa.Column("aggregate_id", sa.UUID(as_uuid=True)),
    sa.Column("event_type", sa.String),
    sa.Column("payload", sa.JSON),
    sa.Column("correlation_id", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("published_at", sa.DateTime(timezone=True)),
)

_material_receipts = sa.Table(
    "material_receipts",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
)

_material_usage = sa.Table(
    "material_usage",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
)

# Extension point: a new domain's aggregate is one entry here — the table
# must expose organization_id, project_id, site_id, occurred_date, occurred_time.
AGGREGATE_TABLES: dict[str, sa.Table] = {
    "material_receipt": _material_receipts,
    "material_usage": _material_usage,
}

# Extension point: a new event type's human summary is one entry here.
EVENT_SUMMARY_BUILDERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "MaterialReceived": lambda p: (
        f"{p.get('quantity')} {p.get('unit')} of {p.get('material_name')} received"
    ),
    "MaterialUsed": lambda p: (
        f"{p.get('quantity')} {p.get('unit')} of {p.get('material_name')} used"
    ),
    "MaterialMovementCorrected": lambda p: (
        f"Material movement corrected ({p.get('movement_reason')})"
    ),
}


def _build_summary(event_type: str, payload: dict[str, Any]) -> str:
    builder = EVENT_SUMMARY_BUILDERS.get(event_type)
    if builder is None:
        return f"{event_type} event"
    try:
        return builder(payload)
    except Exception:  # noqa: BLE001 — a malformed payload must not block the batch
        return f"{event_type} event"


def _coerce_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            return {}
    return {}


async def project_pending_events(conn: AsyncConnection, batch_size: int = 100) -> int:
    """Drain up to `batch_size` unpublished outbox_events into timeline_entries.

    Runs entirely on the caller-supplied connection/transaction so the
    caller (script main(), or a test) controls commit boundaries. Returns
    the number of rows projected (source rows found and inserted into
    timeline_entries — orphaned outbox rows are marked published but not
    counted as "projected").
    """
    select_stmt = (
        sa.select(_outbox_events)
        .where(_outbox_events.c.published_at.is_(None))
        .order_by(_outbox_events.c.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = (await conn.execute(select_stmt)).mappings().all()

    projected = 0
    for row in rows:
        source_table = AGGREGATE_TABLES.get(row["aggregate_type"])
        source = None
        if source_table is not None:
            source = (
                (
                    await conn.execute(
                        sa.select(
                            source_table.c.organization_id,
                            source_table.c.project_id,
                            source_table.c.site_id,
                            source_table.c.occurred_date,
                            source_table.c.occurred_time,
                        ).where(source_table.c.id == row["aggregate_id"])
                    )
                )
                .mappings()
                .first()
            )

        if source is None:
            # Source row not found (shouldn't happen in practice — defensive).
            # Still mark published so a permanently-orphaned row doesn't block
            # the batch forever.
            await conn.execute(
                _outbox_events.update()
                .where(_outbox_events.c.id == row["id"])
                .values(published_at=sa.func.now())
            )
            continue

        payload = _coerce_payload(row["payload"])

        occurred_at = row["created_at"]
        if source["occurred_date"] is not None:
            occurred_at = datetime.datetime.combine(
                source["occurred_date"], source["occurred_time"] or datetime.time.min
            )

        await conn.execute(
            sa.text(
                "INSERT INTO timeline_entries "
                "(id, organization_id, project_id, site_id, event_type, summary, "
                "payload, occurred_at, correlation_id, source_aggregate_type, "
                "source_aggregate_id) "
                "VALUES (:id, :organization_id, :project_id, :site_id, :event_type, "
                ":summary, CAST(:payload AS jsonb), :occurred_at, :correlation_id, "
                ":source_aggregate_type, :source_aggregate_id)"
            ),
            {
                "id": uuid.uuid4(),
                "organization_id": source["organization_id"],
                "project_id": source["project_id"],
                "site_id": source["site_id"],
                "event_type": row["event_type"],
                "summary": _build_summary(row["event_type"], payload),
                "payload": json.dumps(payload),
                "occurred_at": occurred_at,
                "correlation_id": row["correlation_id"],
                "source_aggregate_type": row["aggregate_type"],
                "source_aggregate_id": row["aggregate_id"],
            },
        )
        await conn.execute(
            _outbox_events.update()
            .where(_outbox_events.c.id == row["id"])
            .values(published_at=sa.func.now())
        )
        projected += 1

    return projected
