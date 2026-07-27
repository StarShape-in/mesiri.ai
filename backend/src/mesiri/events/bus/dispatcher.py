"""Generic multi-consumer outbox drain (#14 Event Bus).

One outbox row must be readable by SEVERAL independent consumers (#9
Notifications, #17 Search Index, future ones) without any of them stepping
on each other's progress -- see migration 0450's docstring for why
outbox_events.published_at (timeline_projector.py's own mechanism) can't be
reused for this. `drain_for_consumer` is the anti-join read against
event_consumer_checkpoints described there.

Failure isolation: each row runs inside its own SAVEPOINT (conn.begin_nested()),
not bare try/except. Postgres aborts an entire transaction on any error until
ROLLBACK -- without a savepoint, one consumer raising on row 3 of a 100-row
batch would silently poison every checkpoint INSERT for rows 4-100 too,
since Postgres refuses all further statements in an aborted transaction. The
savepoint contains the damage to exactly the row that failed.

Retry model: a row that fails is simply never checkpointed, so the SAME
anti-join picks it up again on the next drain (next cron invocation -- see
scripts/run_event_consumers.py). No separate backoff/dead-letter subsystem:
this codebase's whole background-work model is "cron re-runs a
drain-to-completion script", which already gives every failed row an
automatic retry every cycle. A row that fails forever blocks nothing else --
SKIP LOCKED and the per-row savepoint both ensure one bad row costs exactly
one wasted attempt per cron tick, not the batch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from .interface import EventConsumer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DrainResult:
    processed: int
    failed: int
    #: How many rows this batch saw (processed + failed) -- callers loop
    #: while this equals the batch size, same convention as
    #: timeline_projector's own project_pending_events / scripts/
    #: project_timeline_events.py's "loop until < batch_size" shape.
    batch_size: int


async def drain_for_consumer(
    conn: AsyncConnection, consumer: EventConsumer, *, batch_size: int = 100
) -> DrainResult:
    """Hand ``consumer`` up to ``batch_size`` outbox rows it hasn't seen yet,
    checkpointing each one it completes successfully. Returns after one
    batch -- callers loop (see scripts/run_event_consumers.py) until a
    drain returns fewer rows than requested."""
    from sqlalchemy import text

    rows = (
        (
            await conn.execute(
                text(
                    "SELECT oe.id, oe.aggregate_type, oe.aggregate_id, oe.event_type, "
                    "oe.payload, oe.correlation_id, oe.created_at "
                    "FROM outbox_events oe "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM event_consumer_checkpoints ecp "
                    "  WHERE ecp.consumer_name = :name AND ecp.event_id = oe.id"
                    ") "
                    "ORDER BY oe.created_at "
                    "LIMIT :batch_size "
                    "FOR UPDATE OF oe SKIP LOCKED"
                ),
                {"name": consumer.name, "batch_size": batch_size},
            )
        )
        .mappings()
        .all()
    )

    processed = 0
    failed = 0
    for row in rows:
        event = dict(row)
        savepoint = await conn.begin_nested()
        try:
            await consumer.handle(conn, event)
            await conn.execute(
                text(
                    "INSERT INTO event_consumer_checkpoints (consumer_name, event_id) "
                    "VALUES (:name, :event_id) ON CONFLICT DO NOTHING"
                ),
                {"name": consumer.name, "event_id": event["id"]},
            )
        except Exception:  # noqa: BLE001 -- one bad row must never block the batch
            await savepoint.rollback()
            logger.exception(
                "event_bus.consumer_failed consumer=%s event_id=%s event_type=%s",
                consumer.name,
                event["id"],
                event.get("event_type"),
            )
            failed += 1
            continue
        else:
            await savepoint.commit()
            processed += 1

    return DrainResult(processed=processed, failed=failed, batch_size=len(rows))
