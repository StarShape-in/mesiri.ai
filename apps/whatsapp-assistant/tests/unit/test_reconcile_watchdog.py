"""Unit tests for the context-sync watchdog (context/reconcile_watchdog.py).

Dashboard project/site assignment changes are projected into the context
layer best-effort -- context/projection_hooks.py swallows failures so a
projection error can't fail the request that caused it. The cost is silent
drift that previously only got fixed if a human ran
scripts/backfill_identity_bridge.py.

The two properties worth guarding here are the ones that make the watchdog
trustworthy rather than just present:

  - it records every outcome, *especially* failures (auto-repair that fails
    silently is the same bug one level up), and
  - only one of the two uvicorn workers actually runs it.

Fakes only -- no live DB.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from context.identity_projection import ReconcileReport
from context.reconcile_watchdog import (
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    TRIGGER_MANUAL,
    TRIGGER_SCHEDULED,
    _env_int,
    _run_once_sync,
    interval_seconds,
    startup_delay_seconds,
    watchdog_enabled,
)


class _FakeRecorder:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


class _FakeConn:
    def __init__(self, *, lock_granted: bool) -> None:
        self._lock_granted = lock_granted
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)

        class _Result:
            def __init__(self, value):
                self._value = value

            def scalar(self):
                return self._value

        if "pg_try_advisory_lock" in sql:
            return _Result(self._lock_granted)
        return _Result(None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeEngine:
    def __init__(self, *, lock_granted: bool = True) -> None:
        self.conn = _FakeConn(lock_granted=lock_granted)

    def connect(self):
        return self.conn


class _FakeService:
    """Stands in for IdentityProjectionService."""

    def __init__(self, *, report=None, raises: Exception | None = None, lock_granted=True) -> None:
        self._engine = _FakeEngine(lock_granted=lock_granted)
        self._report = report if report is not None else ReconcileReport()
        self._raises = raises
        self.reconcile_calls = 0

    def reconcile_all(self):
        self.reconcile_calls += 1
        if self._raises is not None:
            raise self._raises
        return self._report


# ---------------------------------------------------------------------------
# Recording outcomes -- the half that makes failures visible
# ---------------------------------------------------------------------------


def test_clean_run_records_succeeded_with_counts():
    service = _FakeService(
        report=ReconcileReport(organizations=2, users=9, projects=4, sites=6, memberships=7)
    )
    recorder = _FakeRecorder()

    result = _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert result is not None
    assert result["status"] == STATUS_SUCCEEDED
    assert len(recorder.records) == 1
    recorded = recorder.records[0]
    assert recorded["status"] == STATUS_SUCCEEDED
    assert recorded["counts"]["users"] == 9
    assert recorded["errors"] == []
    assert recorded["trigger"] == TRIGGER_SCHEDULED
    # errors must not leak into the counts blob
    assert "errors" not in recorded["counts"]


def test_partial_errors_are_recorded_not_swallowed():
    """A run that repaired most things but hit per-entity errors must not
    read as a clean success -- that's precisely the silent failure this
    whole feature exists to end."""
    service = _FakeService(
        report=ReconcileReport(users=3, errors=["user abc: boom", "site def: nope"])
    )
    recorder = _FakeRecorder()

    result = _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert result["status"] == STATUS_COMPLETED_WITH_ERRORS
    recorded = recorder.records[0]
    assert recorded["status"] == STATUS_COMPLETED_WITH_ERRORS
    assert len(recorded["errors"]) == 2


def test_a_thrown_exception_is_recorded_as_failed_and_does_not_propagate():
    """The watchdog must survive its own failure: if reconcile_all raises,
    that has to land in the run history rather than killing the loop."""
    service = _FakeService(raises=RuntimeError("db gone"))
    recorder = _FakeRecorder()

    result = _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert result["status"] == STATUS_FAILED
    recorded = recorder.records[0]
    assert recorded["status"] == STATUS_FAILED
    assert "db gone" in recorded["errors"][0]
    assert recorded["counts"] is None


def test_duration_is_always_recorded():
    """duration_ms is what makes a slowing reconcile visible before it
    becomes a problem at scale."""
    service = _FakeService()
    recorder = _FakeRecorder()

    _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert recorder.records[0]["duration_ms"] >= 0


def test_failed_run_still_records_duration():
    service = _FakeService(raises=RuntimeError("boom"))
    recorder = _FakeRecorder()

    _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert recorder.records[0]["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# Single-runner election across the two uvicorn workers
# ---------------------------------------------------------------------------


def test_second_worker_skips_when_lock_is_held():
    """infra/mesiri.service runs --workers 2. Without this, both processes
    would run a full re-projection simultaneously every interval."""
    service = _FakeService(lock_granted=False)
    recorder = _FakeRecorder()

    result = _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert result is None
    assert service.reconcile_calls == 0, "the losing worker must not reconcile"
    assert recorder.records == [], "a skipped tick is not a run and must not be recorded"


def test_lock_is_released_after_a_successful_run():
    service = _FakeService()
    recorder = _FakeRecorder()

    _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert any("pg_advisory_unlock" in s for s in service._engine.conn.statements)


def test_lock_is_released_even_when_the_run_fails():
    """A crashed run must not leave the lock held, or every later tick on
    this process would skip forever."""
    service = _FakeService(raises=RuntimeError("boom"))
    recorder = _FakeRecorder()

    _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)

    assert any("pg_advisory_unlock" in s for s in service._engine.conn.statements)


def test_manual_trigger_bypasses_the_lock_entirely():
    """An operator asking for a reconcile must get one, not be silently
    skipped because a scheduled run happened to be in flight."""
    service = _FakeService(lock_granted=False)
    recorder = _FakeRecorder()

    result = _run_once_sync(service, recorder, trigger=TRIGGER_MANUAL, require_lock=False)

    assert result is not None
    assert service.reconcile_calls == 1
    assert recorder.records[0]["trigger"] == TRIGGER_MANUAL
    assert not any("advisory_lock" in s for s in service._engine.conn.statements)


# ---------------------------------------------------------------------------
# Configuration -- tunable without a deploy, safe when misconfigured
# ---------------------------------------------------------------------------


def test_interval_defaults_to_fifteen_minutes(monkeypatch):
    monkeypatch.delenv("MESIRI_RECONCILE__INTERVAL_SECONDS", raising=False)
    assert interval_seconds() == 900


def test_interval_is_environment_tunable(monkeypatch):
    """The answer to "the dataset grew" must be a config change, not a
    code change."""
    monkeypatch.setenv("MESIRI_RECONCILE__INTERVAL_SECONDS", "3600")
    assert interval_seconds() == 3600


def test_interval_is_floored_to_avoid_self_overlap(monkeypatch):
    monkeypatch.setenv("MESIRI_RECONCILE__INTERVAL_SECONDS", "1")
    assert interval_seconds() == 60


def test_a_typo_in_config_falls_back_instead_of_crashing(monkeypatch):
    """A bad value in a deployed .env must not stop the service booting."""
    monkeypatch.setenv("MESIRI_RECONCILE__INTERVAL_SECONDS", "every-15-min")
    assert interval_seconds() == 900


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no"])
def test_watchdog_can_be_disabled(monkeypatch, value):
    monkeypatch.setenv("MESIRI_RECONCILE__ENABLED", value)
    assert watchdog_enabled() is False


def test_watchdog_is_on_by_default(monkeypatch):
    """A safety net you have to opt into is one that won't be on when it
    matters."""
    monkeypatch.delenv("MESIRI_RECONCILE__ENABLED", raising=False)
    assert watchdog_enabled() is True


def test_startup_delay_is_never_negative(monkeypatch):
    monkeypatch.setenv("MESIRI_RECONCILE__STARTUP_DELAY_SECONDS", "-5")
    assert startup_delay_seconds() == 0


def test_env_int_handles_blank(monkeypatch):
    monkeypatch.setenv("SOME_KEY", "   ")
    assert _env_int("SOME_KEY", 42) == 42


# ---------------------------------------------------------------------------
# The loop itself
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_loop_survives_a_failing_tick(monkeypatch):
    """The watchdog is the thing that notices problems -- it must not be
    able to die from one."""
    from context import reconcile_watchdog

    calls = {"n": 0}

    async def _boom(**kwargs):
        calls["n"] += 1
        raise RuntimeError("tick exploded")

    monkeypatch.setattr(reconcile_watchdog, "run_reconcile_once", _boom)
    monkeypatch.setenv("MESIRI_RECONCILE__STARTUP_DELAY_SECONDS", "0")
    monkeypatch.setenv("MESIRI_RECONCILE__INTERVAL_SECONDS", "60")

    task = asyncio.create_task(reconcile_watchdog.watchdog_loop())
    # Let a couple of ticks happen without waiting a real interval.
    for _ in range(3):
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls["n"] >= 1, "the loop must have attempted at least one tick"


@pytest.mark.asyncio
async def test_watchdog_loop_stops_cleanly_on_cancel(monkeypatch):
    from context import reconcile_watchdog

    async def _noop(**kwargs):
        return None

    monkeypatch.setattr(reconcile_watchdog, "run_reconcile_once", _noop)
    monkeypatch.setenv("MESIRI_RECONCILE__STARTUP_DELAY_SECONDS", "0")

    task = asyncio.create_task(reconcile_watchdog.watchdog_loop())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.done()


def test_recorder_failure_does_not_turn_a_good_run_into_a_bad_one():
    """Failing to *record* a successful repair must not report the repair as
    failed -- and must not propagate out of the run at all. Covers the case
    where the 0366 migration hasn't been applied yet, so the insert target
    doesn't exist but the reconcile itself is fine."""
    from context.reconcile_watchdog import ReconcileRunRecorder

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("no db")

    recorder = ReconcileRunRecorder(_BrokenEngine())

    # Direct call must swallow rather than raise.
    recorder.record(
        status=STATUS_SUCCEEDED,
        started_at=datetime.now(UTC),
        duration_ms=5,
        counts={"users": 1},
        errors=[],
        trigger=TRIGGER_SCHEDULED,
    )

    # And a whole run using it still reports the repair honestly.
    service = _FakeService(report=ReconcileReport(users=1))
    result = _run_once_sync(service, recorder, trigger=TRIGGER_SCHEDULED, require_lock=True)
    assert result["status"] == STATUS_SUCCEEDED
    assert service.reconcile_calls == 1


def test_service_is_cached_per_process(monkeypatch):
    """Each IdentityProjectionService builds its own engine and connection
    pool; constructing one per run (every 15 min, forever) would leak pools.

    Counts constructions rather than touching a real database -- the point
    under test is the caching, not the engine.
    """
    from context import reconcile_watchdog

    built = {"n": 0}

    class _CountingService:
        def __init__(self) -> None:
            built["n"] += 1
            self._engine = object()

    monkeypatch.setattr(reconcile_watchdog, "IdentityProjectionService", _CountingService)
    monkeypatch.setattr(reconcile_watchdog, "_service", None)

    first = reconcile_watchdog.get_service()
    second = reconcile_watchdog.get_service()

    assert first is second
    assert built["n"] == 1, "the service (and its connection pool) must be built once"

    # Don't leave the fake cached for other tests in this process.
    monkeypatch.setattr(reconcile_watchdog, "_service", None)
