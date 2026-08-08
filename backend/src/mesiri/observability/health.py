"""Health / readiness orchestration (M1).

Runs each registered dependency's ``check_health`` probe, times it, and folds
the results into a shared :class:`HealthReport`. A failed *required* dependency
makes the whole report UNHEALTHY; a failed optional dependency yields DEGRADED.

Probes never raise out of here — failures become structured status entries. No
credentials or DSNs are ever placed in the report (only user-safe messages).
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.common.health import DependencyState, DependencyStatus, HealthReport


@runtime_checkable
class HealthProbe(Protocol):
    name: str
    required: bool

    async def check_health(self) -> None:
        """Raise :class:`MesiriError` if the dependency is unusable."""
        ...


class HealthChecker:
    def __init__(self, probes: list[HealthProbe]) -> None:
        self._probes = probes

    async def _check_one(self, probe: HealthProbe) -> DependencyStatus:
        required = getattr(probe, "required", True)
        start = time.perf_counter()
        try:
            await probe.check_health()
        except MesiriError as err:
            return DependencyStatus(
                name=probe.name,
                state=DependencyState.UNHEALTHY if required else DependencyState.DEGRADED,
                required=required,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                detail=err.user_safe_message,
                error_code=err.error_code,
            )
        except Exception:  # noqa: BLE001 — never leak raw exceptions
            return DependencyStatus(
                name=probe.name,
                state=DependencyState.UNHEALTHY if required else DependencyState.DEGRADED,
                required=required,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                detail="health probe failed",
                error_code="INTERNAL_ERROR",
            )
        return DependencyStatus(
            name=probe.name,
            state=DependencyState.HEALTHY,
            required=required,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def readiness(self) -> HealthReport:
        statuses = [await self._check_one(p) for p in self._probes]
        return HealthReport.aggregate(statuses)
