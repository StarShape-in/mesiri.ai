"""Durable job queue for WhatsApp ingress processing (ARQ on top of Redis).

Replaces the previous `asyncio.create_task` handoff, which held the only
copy of an in-flight message in this process's memory: a crash or restart
between "claimed" and "done" lost the message outright, with nothing left
to recover it. A claimed message is now written here as an ARQ job -- a
durable Redis entry independent of any one process -- and a separate worker
process (worker.py) is the thing that actually runs it. If the worker dies
mid-job, the job is still sitting in Redis for the next worker to pick up.

Only wired in when a real Redis is configured (MESIRI_REDIS__HOST set, same
condition dependencies.py already uses for RedisClient vs FakeRedis) --
FakeRedis has no persistent backing store, so there is nothing for ARQ to
durably queue against in dev/test. Those environments keep the previous
in-process asyncio.create_task behaviour (see receiver.py's `enqueue=None`
default).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arq import create_pool
from arq.connections import ArqRedis
from arq.connections import RedisSettings as ArqRedisSettings

from ingress.receiver import MessageIngressContext

if TYPE_CHECKING:
    from mesiri.bootstrap.settings import RedisSettings

logger = logging.getLogger(__name__)

# The job function name ARQ dispatches to -- must match the function name
# registered in worker.WorkerSettings.functions.
PROCESS_MESSAGE_JOB = "process_claimed_message_job"

# ARQ's own queue key inside Redis. Namespaced so it can never collide with
# the unrelated JSON keys the rest of the app writes through the same Redis
# instance (active context, dedup claims, plan store, ...).
QUEUE_NAME = "mesiri:whatsapp:ingress"

# ARQ's Worker writes a small text status to this key on every tick, TTL'd to
# just past the interval below (see arq.worker.Worker.record_health) -- so
# the key's mere presence already proves the worker was alive within the
# last HEALTH_CHECK_INTERVAL_SECONDS, no timestamp parsing required. Both
# worker.py (which writes it) and admin/queue_router.py (which reads it,
# no SSH needed) import these two constants so they can never drift apart.
HEALTH_CHECK_KEY = f"{QUEUE_NAME}:health-check"
# ARQ's own default is 3600s -- far too stale for a "is it up right now"
# dashboard. 30s keeps the check responsive without hammering Redis.
HEALTH_CHECK_INTERVAL_SECONDS = 30

_HEALTH_CHECK_PATTERN = re.compile(
    r"j_complete=(?P<complete>\d+) j_failed=(?P<failed>\d+) "
    r"j_retried=(?P<retried>\d+) j_ongoing=(?P<ongoing>\d+) queued=(?P<queued>\d+)"
)


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    """Parsed form of ARQ's own health-check string."""

    raw: str
    jobs_complete: int
    jobs_failed: int
    jobs_retried: int
    jobs_ongoing: int
    queue_depth: int


def parse_worker_health(raw: str) -> WorkerHealth | None:
    """Parse ARQ's `record_health` text -- returns None if the format ever
    changes underneath us (unsupported ARQ version) rather than raising, so
    the admin endpoint can still report "worker alive, details unavailable"
    instead of 500ing."""
    match = _HEALTH_CHECK_PATTERN.search(raw)
    if match is None:
        return None
    return WorkerHealth(
        raw=raw,
        jobs_complete=int(match["complete"]),
        jobs_failed=int(match["failed"]),
        jobs_retried=int(match["retried"]),
        jobs_ongoing=int(match["ongoing"]),
        queue_depth=int(match["queued"]),
    )


def arq_redis_settings(redis_settings: RedisSettings) -> ArqRedisSettings:
    """Translate the app's RedisSettings into ARQ's own settings type.

    ARQ opens its own connection pool (it needs one distinct from
    RedisClient's json-string-oriented one), but points at the exact same
    Redis instance/db -- there is only one Redis in this deployment.
    """
    return ArqRedisSettings(
        host=redis_settings.host,
        port=redis_settings.port,
        database=redis_settings.db,
        password=(
            redis_settings.password.get_secret_value() if redis_settings.password else None
        ),
        conn_timeout=int(redis_settings.connect_timeout_seconds),
    )


class MessageEnqueuer:
    """Writes a claimed message's replayable envelope into the ARQ queue.

    Callable so it drops straight into WhatsAppReceiver's `enqueue` hook
    (ingress/receiver.py). Owns its own connect()/disconnect() lifecycle --
    same pattern as redis_client and material_db (see runtime/lifecycle.py)
    -- because build_container() itself is synchronous and can't await
    opening the ARQ pool; the lifespan handler connects it after the
    container is built, same as everything else with a live connection.
    """

    def __init__(self, redis_settings: RedisSettings) -> None:
        self._redis_settings = redis_settings
        self._pool: ArqRedis | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await create_pool(
            arq_redis_settings(self._redis_settings), default_queue_name=QUEUE_NAME
        )

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    async def __call__(self, context: MessageIngressContext) -> None:
        if self._pool is None:
            raise RuntimeError("MessageEnqueuer used before connect()")
        envelope = {
            "message": dict(context.message),
            "contacts": [dict(c) for c in context.contacts],
            "phone_number_id": context.phone_number_id,
            "display_phone_number": context.display_phone_number,
        }
        message_id = str(context.message.get("id") or "unknown")
        await self._pool.enqueue_job(
            PROCESS_MESSAGE_JOB,
            envelope,
            _job_id=f"whatsapp-ingress:{message_id}",
            _queue_name=QUEUE_NAME,
        )
        logger.info("whatsapp.ingress_enqueued message_id=%s", message_id)


def context_from_envelope(envelope: dict) -> MessageIngressContext:
    """Inverse of MessageEnqueuer's envelope -- rebuilds the context a job
    payload carries so worker.py can hand it back to the receiver."""
    return MessageIngressContext(
        message=envelope["message"],
        contacts=tuple(envelope.get("contacts") or ()),
        phone_number_id=envelope.get("phone_number_id"),
        display_phone_number=envelope.get("display_phone_number"),
    )
