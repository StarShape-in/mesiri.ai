"""Periodic context-sync watchdog — repairs identity drift and records itself.

Assignment changes made on the dashboard are projected into the context layer
on every write, but that projection is deliberately best-effort:
context/projection_hooks.py swallows failures so a projection error can't
fail the request that caused it. The cost is silent drift -- the assistant
keeps resolving a user against stale project/site assignments, and nobody
finds out until someone manually runs scripts/backfill_identity_bridge.py.

`IdentityProjectionService.reconcile_all()` already repairs that and is
idempotent. This module supplies the two things that were missing:

1. Something that runs it on a schedule, without a human.
2. A record of every run, so a *failing watchdog* is visible instead of
   being the same silent failure one level up. Auto-repair alone would just
   move the blind spot.

Two operational constraints shape the design:

- The service runs under `uvicorn --workers 2` (infra/mesiri.service), so a
  naive timer in the app would fire twice. A Postgres advisory lock elects a
  single runner per interval; it's released automatically if the process
  dies, which a table-based flag would not be.
- `reconcile_all()` re-projects every entity in one transaction, so its cost
  grows with tenant count. `duration_ms` is persisted on every run to make
  that trend visible early -- see the interval settings below, which are
  environment-tunable precisely so the answer to "it got slow" isn't a code
  change.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .identity_projection import IdentityProjectionService

_log = logging.getLogger("mesiri.context.reconcile")

# Arbitrary but fixed: two processes must derive the same key to contend for
# the same lock. Advisory locks live in their own namespace and never touch
# table data.
_ADVISORY_LOCK_KEY = 0x1DE7_1F79  # "identity" -- mnemonic only

# Cap what one pathological run can write into the errors column.
_MAX_RECORDED_ERRORS = 50

STATUS_SUCCEEDED = "succeeded"
STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATUS_FAILED = "failed"

TRIGGER_SCHEDULED = "scheduled"
TRIGGER_MANUAL = "manual"


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back on anything unusable.

    Never raises: a typo in a deployed .env must not stop the service from
    booting, and the default is always a safe interval.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        _log.warning("reconcile.bad_env name=%s value=%r using default=%s", name, raw, default)
        return default
    return value


def watchdog_enabled() -> bool:
    """Off only if explicitly disabled. A safety net that needs opting into
    is one that won't be on when it matters."""
    return os.environ.get("MESIRI_RECONCILE__ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


def interval_seconds() -> int:
    """How long to wait between runs. Environment-tunable so the response to
    a growing dataset is a config change, not a deploy."""
    value = _env_int("MESIRI_RECONCILE__INTERVAL_SECONDS", 900)  # 15 minutes
    # A pathologically small interval would have runs overlapping themselves;
    # the advisory lock makes that safe rather than corrupting, but it's
    # still pure load. Floor it.
    return max(value, 60)


def startup_delay_seconds() -> int:
    """Grace period before the first run, so a deploy's first request isn't
    competing with a full re-projection."""
    return max(_env_int("MESIRI_RECONCILE__STARTUP_DELAY_SECONDS", 60), 0)


class ReconcileRunRecorder:
    """Persists one row per reconcile attempt to identity_reconcile_runs.

    Uses the projection service's own synchronous engine rather than the
    async PostgresDatabase: this runs in the same worker thread as
    reconcile_all() itself, and sharing the engine keeps the watchdog to a
    single connection source.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record(
        self,
        *,
        status: str,
        started_at: datetime,
        duration_ms: int,
        counts: dict[str, int] | None,
        errors: list[str],
        trigger: str,
    ) -> None:
        """Write the run row. Never raises -- failing to *record* a
        successful repair must not turn it into a failed one."""
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO identity_reconcile_runs "
                        "(id, status, started_at, finished_at, duration_ms, counts, "
                        " error_count, errors, trigger) "
                        "VALUES (:id, :status, :started_at, now(), :duration_ms, "
                        " CAST(:counts AS jsonb), :error_count, CAST(:errors AS jsonb), :trigger)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "status": status,
                        "started_at": started_at,
                        "duration_ms": duration_ms,
                        "counts": json.dumps(counts or {}),
                        "error_count": len(errors),
                        "errors": json.dumps(errors[:_MAX_RECORDED_ERRORS]),
                        "trigger": trigger,
                    },
                )
        except Exception:  # noqa: BLE001
            _log.exception("reconcile.record_failed status=%s", status)


def _run_once_sync(
    service: IdentityProjectionService,
    recorder: ReconcileRunRecorder,
    *,
    trigger: str,
    require_lock: bool,
) -> dict[str, Any] | None:
    """Blocking body of one reconcile attempt. Returns a summary, or None if
    another worker held the lock (not an error -- exactly one runner is the
    intended outcome).

    `require_lock` is False for a manual admin trigger: an operator asking
    for a reconcile right now should get one, not be silently skipped
    because the scheduled run happened to be mid-flight.
    """
    engine = service._engine  # noqa: SLF001 — same package, deliberate reuse
    started_at = datetime.now(UTC)
    started_perf = time.perf_counter()

    conn_ctx = engine.connect()
    with conn_ctx as lock_conn:
        if require_lock:
            acquired = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
            ).scalar()
            if not acquired:
                _log.debug("reconcile.skipped_lock_held")
                return None
        try:
            try:
                report = service.reconcile_all()
            except Exception as exc:  # noqa: BLE001
                duration_ms = int((time.perf_counter() - started_perf) * 1000)
                _log.exception("reconcile.failed trigger=%s", trigger)
                recorder.record(
                    status=STATUS_FAILED,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    counts=None,
                    errors=[f"{type(exc).__name__}: {exc}"],
                    trigger=trigger,
                )
                return {
                    "status": STATUS_FAILED,
                    "duration_ms": duration_ms,
                    "counts": {},
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }

            duration_ms = int((time.perf_counter() - started_perf) * 1000)
            counts = {k: v for k, v in asdict(report).items() if k != "errors"}
            status = STATUS_COMPLETED_WITH_ERRORS if report.errors else STATUS_SUCCEEDED
            recorder.record(
                status=status,
                started_at=started_at,
                duration_ms=duration_ms,
                counts=counts,
                errors=list(report.errors),
                trigger=trigger,
            )
            if report.errors:
                _log.warning(
                    "reconcile.completed_with_errors trigger=%s errors=%s duration_ms=%s",
                    trigger,
                    len(report.errors),
                    duration_ms,
                )
            else:
                _log.info(
                    "reconcile.succeeded trigger=%s duration_ms=%s counts=%s",
                    trigger,
                    duration_ms,
                    counts,
                )
            return {
                "status": status,
                "duration_ms": duration_ms,
                "counts": counts,
                "errors": list(report.errors),
            }
        finally:
            if require_lock:
                lock_conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_LOCK_KEY}
                )


_service: IdentityProjectionService | None = None


def get_service() -> IdentityProjectionService:
    """One projection service (and therefore one engine + connection pool)
    per process.

    Constructing IdentityProjectionService calls build_sync_engine(), which
    creates a whole new engine and pool. Doing that per run -- every 15
    minutes, forever -- would leak pools for the life of the process, so the
    instance is cached here the same way context/projection_hooks.py caches
    its own.
    """
    global _service
    if _service is None:
        _service = IdentityProjectionService()
    return _service


async def run_reconcile_once(
    *,
    trigger: str = TRIGGER_MANUAL,
    require_lock: bool = False,
    service: IdentityProjectionService | None = None,
) -> dict[str, Any] | None:
    """Run one reconcile off the event loop (the projection service is
    synchronous, same as context/projection_hooks.py's use of to_thread)."""
    svc = service or get_service()
    recorder = ReconcileRunRecorder(svc._engine)  # noqa: SLF001 — same package
    return await asyncio.to_thread(
        _run_once_sync, svc, recorder, trigger=trigger, require_lock=require_lock
    )


async def watchdog_loop(*, service: IdentityProjectionService | None = None) -> None:
    """Forever-loop driving the scheduled reconcile. Cancelled on shutdown.

    Every failure mode is swallowed and retried on the next tick: this is the
    thing that exists to notice problems, so it must not be able to die from
    one. The only exception that escapes is CancelledError, which is how
    shutdown asks it to stop.
    """
    delay = startup_delay_seconds()
    _log.info(
        "reconcile.watchdog_starting interval_seconds=%s startup_delay_seconds=%s",
        interval_seconds(),
        delay,
    )
    try:
        await asyncio.sleep(delay)
        while True:
            try:
                await run_reconcile_once(
                    trigger=TRIGGER_SCHEDULED, require_lock=True, service=service
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _log.exception("reconcile.watchdog_tick_failed")
            # Re-read each tick so a changed interval takes effect without a
            # restart.
            await asyncio.sleep(interval_seconds())
    except asyncio.CancelledError:
        _log.info("reconcile.watchdog_stopped")
        raise
