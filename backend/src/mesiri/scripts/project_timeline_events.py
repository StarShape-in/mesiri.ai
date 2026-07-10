"""Drains outbox_events into timeline_entries (materials scope only, M-Timeline).

Invocable manually or via a cron entry — not a background worker service
(same convention as mesiri.application.materials.recovery). Loops batches
until a batch returns 0 projected rows (i.e. catches up fully in one run),
so a cron cadence of e.g. every 1-2 minutes keeps the timeline near-real-time
without needing a persistent process.

Recommended VPS crontab entry (ops-managed, not tracked in this repo):
    * * * * * cd /opt/mesiri/backend && \
        PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:/opt/mesiri/backend/src \
        /opt/mesiri/.venv/bin/python -m mesiri.scripts.project_timeline_events \
        >> /var/log/mesiri/timeline-projector.log 2>&1

Run:  make project-timeline   (or)  python -m mesiri.scripts.project_timeline_events
"""

from __future__ import annotations

import asyncio
import sys

from ..bootstrap.settings import Settings
from ..events.consumers.timeline_projector import project_pending_events
from ..infrastructure.postgres.database import PostgresDatabase


async def run() -> int:
    """Drain all pending outbox_events, batch by batch. Returns total projected."""
    settings = Settings()
    db = PostgresDatabase(settings.postgres)
    await db.connect()
    total = 0
    try:
        while True:
            async with db.transaction() as conn:
                count = await project_pending_events(conn, batch_size=100)
            total += count
            if count < 100:
                break
    finally:
        await db.disconnect()
    return total


def main() -> int:
    total = asyncio.run(run())
    print(f"timeline-projector: projected {total} event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
