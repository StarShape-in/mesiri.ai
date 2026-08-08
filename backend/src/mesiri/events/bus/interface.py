"""EventConsumer -- the contract a NEW outbox reader satisfies (#14 Event Bus).

Deliberately narrow: one async method, no lifecycle hooks, no
subscribe/unsubscribe machinery. A consumer is invoked once per unprocessed
outbox row it's handed; it either completes (checkpointed by the dispatcher)
or raises (left unchecked, picked up again on the next drain -- see
dispatcher.py's docstring on why that's sufficient retry for this codebase's
cron-invoked, drain-to-completion model, without a separate retry/backoff
subsystem).

Does NOT replace timeline_projector.py, which keeps using
outbox_events.published_at exactly as before -- this protocol and its
dispatcher are for every consumer AFTER the first, which needs its own
independent read progress (see migration 0450's docstring for why).
"""

from __future__ import annotations

from typing import Any, Protocol


class EventConsumer(Protocol):
    """One named, independent reader of the outbox stream."""

    #: Stable identifier -- the checkpoint key in event_consumer_checkpoints.
    #: Renaming this loses the consumer's place and replays its entire
    #: backlog, so treat it as durable, like a database column name.
    name: str

    async def handle(self, conn: Any, event: dict[str, Any]) -> None:
        """Process one outbox_events row (as a plain dict -- id, aggregate_type,
        aggregate_id, event_type, payload, correlation_id, created_at).

        Runs inside the SAME transaction the dispatcher used to claim the
        row -- a consumer that also writes to the database gets that write
        committed atomically with its own checkpoint, or rolled back
        together with it if either fails. Must not commit or roll back the
        connection itself; the dispatcher owns the transaction boundary.
        """
        ...
