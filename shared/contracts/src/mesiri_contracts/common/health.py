"""Health / readiness contracts (M0).

Shared shape for dependency and aggregate health so the health endpoints, the
golden scenario, and observability all agree on the format. Contains no
secrets — safe to expose over the wire.

Ownership: SHARED ARCHITECTURE.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DependencyState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"       # reachable but impaired / optional dependency down
    UNHEALTHY = "unhealthy"     # required dependency unreachable
    UNKNOWN = "unknown"         # not checked (e.g. provider represented by config)


class DependencyStatus(BaseModel):
    name: str
    state: DependencyState
    required: bool = True
    latency_ms: float | None = None
    detail: str | None = None      # user-safe only — never credentials
    error_code: str | None = None


class HealthReport(BaseModel):
    """Aggregate readiness across all checked dependencies."""

    state: DependencyState
    dependencies: list[DependencyStatus] = Field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return self.state == DependencyState.HEALTHY

    @classmethod
    def aggregate(cls, dependencies: list[DependencyStatus]) -> HealthReport:
        """A report is UNHEALTHY if any *required* dependency is unhealthy,
        DEGRADED if only optional dependencies are impaired, else HEALTHY."""
        state = DependencyState.HEALTHY
        for dep in dependencies:
            if dep.state == DependencyState.UNHEALTHY and dep.required:
                state = DependencyState.UNHEALTHY
                break
            if dep.state in (DependencyState.UNHEALTHY, DependencyState.DEGRADED):
                # optional impairment -> degraded, but keep scanning for a
                # required-unhealthy which outranks it.
                state = DependencyState.DEGRADED
        return cls(state=state, dependencies=dependencies)
