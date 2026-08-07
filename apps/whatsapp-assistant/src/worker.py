"""ARQ worker process: consumes jobs enqueued by runtime/queue.py.

Deployed as a second, independent systemd unit alongside the FastAPI process
(see infra/mesiri-worker.service) -- the web process only ever enqueues now
(ingress/receiver.py, when a real Redis is configured); this process is what
actually runs the WhatsApp journey (media download, understanding, context,
planner, workflow, reply).

Run locally with:  arq worker.WorkerSettings
"""

from __future__ import annotations

import logging

import httpx

from mesiri.bootstrap.settings import get_settings as get_backend_settings
from runtime.dependencies import Settings, build_container
from runtime.queue import QUEUE_NAME, arq_redis_settings, context_from_envelope

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def startup(ctx: dict) -> None:
    """Build this worker's own dependency container.

    Deliberately the exact same `build_container` the FastAPI process uses
    (runtime/lifecycle.py) -- a worker is just another process wiring up the
    same dependency graph, not a special-cased subset of it. Each process
    (uvicorn workers included) gets its own DB pool / Redis connection /
    http client; nothing here is shared across processes.
    """
    configure_logging()
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=30.0)
    container = build_container(settings, http_client)
    await container.redis_client.connect()
    await container.material_db.connect()

    ctx["http_client"] = http_client
    ctx["container"] = container
    logger.info("whatsapp.worker_started")


async def shutdown(ctx: dict) -> None:
    container = ctx.get("container")
    if container is not None:
        await container.material_db.disconnect()
        await container.redis_client.disconnect()
        await container.receipt_renderer.close()
    http_client = ctx.get("http_client")
    if http_client is not None:
        await http_client.aclose()
    logger.info("whatsapp.worker_stopped")


async def process_claimed_message_job(ctx: dict, envelope: dict) -> None:
    """The ARQ job function -- name must match runtime/queue.py's
    PROCESS_MESSAGE_JOB, which is what enqueue_job() dispatches by."""
    container = ctx["container"]
    context = context_from_envelope(envelope)
    message_id = str(context.message.get("id") or "unknown")
    logger.info("whatsapp.ingress_job_started message_id=%s", message_id)
    await container.receiver.process_claimed_message(context)
    logger.info("whatsapp.ingress_job_finished message_id=%s", message_id)


class WorkerSettings:
    """ARQ worker configuration, picked up by the `arq` CLI entrypoint."""

    functions = [process_claimed_message_job]
    on_startup = startup
    on_shutdown = shutdown

    # Same Redis instance as the web process's enqueuer -- computed from the
    # backend settings (MESIRI_REDIS__* env vars), same as RedisClient uses.
    redis_settings = arq_redis_settings(get_backend_settings().redis)
    queue_name = QUEUE_NAME

    # Retries are for real infra hiccups (a DB blip, a provider 503) -- not
    # for repeatedly reprocessing a message that fails deterministically.
    # 3 keeps a bad message from hammering downstream providers forever
    # while still surviving one or two transient failures.
    max_tries = 3
    # The full journey (STT/vision -> extraction -> DB -> reply) has been
    # observed taking several seconds on media messages; this bounds a
    # stuck job well above that without letting one hang indefinitely.
    job_timeout = 120
