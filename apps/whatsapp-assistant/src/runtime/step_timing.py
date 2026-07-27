"""Per-step timing for the inbound journey's pre-pipeline block (diagnostic).

Exists to answer one question: traced image messages showed 6-11s between the
``ingress`` stage and the ``understanding`` stage -- larger than every AI call
combined -- and that window is ~600 lines of sequential fast-path checks in
runtime/dependencies.py's ``_run_journey``, each doing its own database or
Redis work to discover "not applicable". This records how long each one
actually takes, so the fix targets the real cost rather than the
likeliest-looking one.

A lap stopwatch rather than a per-call wrapper on purpose: laps are
single-line insertions between existing statements, so instrumenting a
600-line function needs no re-indentation and cannot restructure a
multi-line call. It also means time spent *between* the named calls is
attributed to the following lap instead of vanishing -- which is the point,
since we don't yet know that the named calls are where the time goes.

Deliberately small and self-contained: this is scaffolding for a specific
investigation, so when the pre-pipeline block stops being the bottleneck this
module and its call sites come out together.
"""

from __future__ import annotations

import time
from typing import Any


class StepTimer:
    """Lap stopwatch accumulating named step durations (ms) for one message."""

    def __init__(self) -> None:
        self._steps: dict[str, float] = {}
        self._t0 = time.perf_counter()
        self._last = self._t0

    def lap(self, name: str) -> None:
        """Record milliseconds elapsed since the previous lap (or since the
        timer was created, for the first one).

        A repeated name accumulates rather than overwriting, so a lap inside a
        loop reports total time spent there instead of just its last pass.
        """
        now = time.perf_counter()
        elapsed = round((now - self._last) * 1000, 1)
        self._steps[name] = round(self._steps.get(name, 0.0) + elapsed, 1)
        self._last = now

    @property
    def steps(self) -> dict[str, Any]:
        """Recorded laps, ordered worst-first so the payload reads as a
        ranking in the logs viewer.

        ``_unaccounted_ms`` is included deliberately: it's the wall time not
        claimed by any lap. Finding the last gap took manually subtracting
        trace timestamps by hand, so the number that matters most is stated
        outright rather than left to be derived -- if it's large, the cost is
        somewhere nothing is measuring yet, which is exactly when it's
        easiest to look in the wrong place.
        """
        ranked = dict(sorted(self._steps.items(), key=lambda kv: kv[1], reverse=True))
        unaccounted = round(self.total_ms - sum(self._steps.values()), 1)
        return {"_unaccounted_ms": unaccounted, **ranked}

    @property
    def total_ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)
