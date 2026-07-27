"""Drains the outbox for every registered #14 Event Bus consumer.

Does NOT touch timeline_projector.py -- that consumer predates the bus and
keeps running unchanged via `python -m mesiri.scripts.project_timeline_events`
(its own cron entry, its own mechanism: outbox_events.published_at). This
script is for every consumer built AFTER the bus (#9 Notifications, #17
Search Index, ...), each reading the same outbox independently via
event_consumer_checkpoints (migration 0450).

Invocable manually or via a cron entry -- not a persistent worker service,
same convention as project_timeline_events.py and
mesiri.application.materials.recovery. Loops each consumer's batches until
one returns fewer rows than requested (i.e. catches up fully in one run).

Recommended VPS crontab entry (ops-managed, not tracked in this repo):
    * * * * * cd /opt/mesiri/backend && \
        PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:/opt/mesiri/backend/src \
        /opt/mesiri/.venv/bin/python -m mesiri.scripts.run_event_consumers \
        >> /var/log/mesiri/event-consumers.log 2>&1

Run:  python -m mesiri.scripts.run_event_consumers
"""

from __future__ import annotations

import asyncio
import sys

from ..bootstrap.settings import Settings
from ..events.bus import EventConsumer, drain_for_consumer
from ..infrastructure.postgres.database import PostgresDatabase

_BATCH_SIZE = 100


def _registered_consumers() -> list[EventConsumer]:
    """Every #14 Event Bus consumer this process drains.

    A function, not a module-level constant, so a consumer's own module
    (and whatever it imports) is only pulled in when this script actually
    runs -- not eagerly at import time by every caller of mesiri.events.bus.
    Empty until the first consumer built on top of the bus registers here
    (#9 Notifications, #17 Search Index).
    """
    return []


async def run() -> dict[str, int]:
    """Drain every registered consumer to completion. Returns {consumer_name: total_processed}."""
    settings = Settings()
    db = PostgresDatabase(settings.postgres)
    await db.connect()
    totals: dict[str, int] = {}
    try:
        for consumer in _registered_consumers():
            total = 0
            while True:
                async with db.transaction() as conn:
                    result = await drain_for_consumer(conn, consumer, batch_size=_BATCH_SIZE)
                total += result.processed
                if result.batch_size < _BATCH_SIZE:
                    break
            totals[consumer.name] = total
    finally:
        await db.disconnect()
    return totals


def main() -> int:
    totals = asyncio.run(run())
    if not totals:
        print("event-consumers: no consumers registered yet")
    for name, count in totals.items():
        print(f"event-consumers: {name} processed {count} event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
