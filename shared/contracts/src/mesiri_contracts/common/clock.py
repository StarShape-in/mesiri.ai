"""Clock abstraction (M0).

Business and infrastructure code depends on the :class:`Clock` protocol rather
than calling ``datetime.now`` directly, so time is injectable and tests are
deterministic.

Ownership: SHARED ARCHITECTURE.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC ``datetime``."""
        ...


class SystemClock:
    """Real wall-clock time (UTC)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests."""

    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def set(self, moment: datetime) -> None:
        self._moment = moment
