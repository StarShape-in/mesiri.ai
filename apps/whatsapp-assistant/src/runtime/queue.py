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
