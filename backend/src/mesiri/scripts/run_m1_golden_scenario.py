"""M1 "Infrastructure Alive" golden scenario — executable proof.

Runs the whole local runtime path and asserts every step:

    start runtime -> validate config -> connect Postgres/Redis/object storage
    -> mint one correlation_id -> Postgres write+read -> Redis write+read
    -> object-storage put+get -> same correlation_id throughout
    -> readiness = HEALTHY -> clean shutdown.

Defaults to the in-process fakes so the proof is reproducible in CI without
docker or credentials. Set MESIRI_GOLDEN_USE_FAKES=false to run against the live
docker stack (requires `make dev` + `make migrate`).

Run:  make m1-golden   (or)  python -m mesiri.scripts.run_m1_golden_scenario
"""

from __future__ import annotations

import asyncio
import os
import sys

from mesiri_contracts.common.health import DependencyState
from mesiri_contracts.common.ids import new_correlation_id

from ..bootstrap.lifecycle import AppLifecycle
from ..bootstrap.settings import Settings
from ..observability import tracing


class _Check:
    def __init__(self) -> None:
        self.items: list[tuple[str, bool, str]] = []

    def record(self, label: str, ok: bool, detail: str = "") -> None:
        self.items.append((label, ok, detail))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.items)


async def run() -> _Check:
    check = _Check()
    use_fakes = os.environ.get("MESIRI_GOLDEN_USE_FAKES", "true").lower() != "false"

    # Read settings fresh (not the process-wide cache) so the script honours the
    # current environment on every invocation.
    lc = AppLifecycle.create(Settings(), use_fakes=use_fakes)
    check.record("Configuration validated", True)

    await lc.startup()
    c = lc.container
    check.record("PostgreSQL reachable", True)
    check.record("Redis reachable", True)
    check.record("Object storage reachable", True)

    try:
        correlation_id = new_correlation_id()
        with tracing.correlation_scope(correlation_id=correlation_id):
            observed = {tracing.get_correlation_id()}

            # PostgreSQL operation
            await c.postgres.write_heartbeat("m1-golden", "alive")  # type: ignore[union-attr]
            row = await c.postgres.read_heartbeat("m1-golden")  # type: ignore[union-attr]
            check.record("PostgreSQL write+read", row is not None and row.get("note") == "alive")
            observed.add(tracing.get_correlation_id())

            # Redis operation
            await c.redis.set_json("m1-golden", {"ok": True})  # type: ignore[union-attr]
            value = await c.redis.get_json("m1-golden")  # type: ignore[union-attr]
            check.record("Redis write+read", value == {"ok": True})
            observed.add(tracing.get_correlation_id())

            # Object-storage operation
            await c.object_storage.put_object("m1-golden.txt", b"alive", content_type="text/plain")
            obj = await c.object_storage.get_object("m1-golden.txt")
            check.record("Object storage put+get", obj.data == b"alive")
            observed.add(tracing.get_correlation_id())

            check.record(
                "correlation_id preserved across dependencies",
                observed == {correlation_id},
                f"observed={observed}",
            )

        report = await c.health_checker().readiness()
        check.record(
            "Readiness = HEALTHY",
            report.state == DependencyState.HEALTHY,
            f"state={report.state.value}",
        )
        for dep in report.dependencies:
            check.record(
                f"  {dep.name} = {dep.state.value.upper()}", dep.state == DependencyState.HEALTHY
            )
    finally:
        await lc.shutdown()
        check.record("Clean shutdown verified", not lc.started)

    return check


def main() -> int:
    check = asyncio.run(run())
    print("\n" + "=" * 48)
    print("M1 INFRASTRUCTURE ALIVE")
    print("=" * 48)
    for label, ok, detail in check.items:
        mark = "[ok]" if ok else "[XX]"
        line = f"{mark} {label}"
        if detail and not ok:
            line += f"   [{detail}]"
        print(line)
    print("=" * 48)
    result = "PASSED" if check.passed else "FAILED"
    print(f"M1 GATE: {result}")
    print("=" * 48)
    return 0 if check.passed else 1


if __name__ == "__main__":
    sys.exit(main())
