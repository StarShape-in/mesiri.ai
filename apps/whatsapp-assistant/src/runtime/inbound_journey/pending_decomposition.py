"""Redis-backed pending decomposition (short-lived, pop-once).

docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §14: "the single-message
material/project/site/stock gates never re-run per decomposed segment."
This closes the project/site half of that gap, and (Phase A5 of
docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md) the material/unit/stock
half too.

Project/site ambiguity is a property of the SENDER, not of any one segment
-- the same `actor.projects`/`actor.sites` apply to every segment of one
decomposed message, so it is resolved exactly ONCE for the whole
decomposition, before any segment is canonicalized, rather than per
segment. When it can't be resolved automatically (the sender has more than
one project, or the resolved project has more than one site), the already-
decomposed segments are held here while a picker asks -- mirroring
interactions/pending_report.py's store/pop-once pattern exactly, generalized
from one CanonicalEventV2 to the list of segment texts a decomposed message
produced.

Material-unit/stock ambiguity IS genuinely per-segment (an ambiguous catalog
name or an over-stock usage report depends on that one segment's own
fields, never the sender as a whole) -- ``built_events``/``pending_event``
below hold that state: every earlier segment that already fully passed
every gate (``built_events``), and the ONE segment currently paused
mid-resolution (``pending_event``) -- e.g. its own ``material_id`` still
unset while a material picker is on screen. ``segments`` holds only what
comes AFTER the paused one; the paused one itself is never re-decomposed or
re-extracted on resume, exactly for the reason the module docstring above
already gives for the whole-decomposition case.
"""

from __future__ import annotations

from typing import Any, Protocol

from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

_DEFAULT_TTL_SECONDS = 600  # 10 minutes -- matches PendingReportStore's own reasoning


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class PendingDecomposition:
    """What is held while a project/site picker, or a material/unit/stock
    gate's own picker, is answered.

    ``segments``: the segment texts not yet processed at all -- decompose()'s
    own output, never re-decomposed on resume (a second call could risk a
    different split for the same message). For a project/site pause this is
    every segment; for a material/unit/stock pause (Phase A5) this is only
    the segments AFTER the one currently paused.

    ``resolved``: the context at the time of holding, so a later gate sees
    whatever an earlier one already resolved (a picked project_id, etc.).

    ``expense_categories``: passed through unchanged to every per-segment
    extraction call.

    ``built_events``: every earlier segment that has ALREADY passed every
    gate, in order -- Phase A5 only. Empty for a project/site pause (nothing
    has been canonicalized yet at that point).

    ``pending_event``: the ONE segment currently paused mid-gate -- Phase A5
    only. ``None`` for a project/site pause (there is no single segment in
    play yet); set for a material/unit/stock pause, so the resume leg
    mutates and re-gates THIS event rather than rebuilding it from its
    original text (which would silently discard whatever the gate chain had
    already resolved on it, e.g. a project_id from an earlier StepRef-free
    binding).
    """

    __slots__ = ("segments", "resolved", "expense_categories", "built_events", "pending_event")

    def __init__(
        self,
        *,
        segments: tuple[str, ...],
        resolved: ResolvedContextV2,
        expense_categories: tuple[str, ...] | None,
        built_events: tuple[CanonicalEventV2, ...] = (),
        pending_event: CanonicalEventV2 | None = None,
    ) -> None:
        self.segments = segments
        self.resolved = resolved
        self.expense_categories = expense_categories
        self.built_events = built_events
        self.pending_event = pending_event

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": list(self.segments),
            "resolved": self.resolved.model_dump(mode="json"),
            "expense_categories": list(self.expense_categories)
            if self.expense_categories is not None
            else None,
            "built_events": [e.model_dump(mode="json") for e in self.built_events],
            "pending_event": self.pending_event.model_dump(mode="json")
            if self.pending_event is not None
            else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PendingDecomposition:
        return cls(
            segments=tuple(raw["segments"]),
            resolved=ResolvedContextV2.model_validate(raw["resolved"]),
            expense_categories=tuple(raw["expense_categories"])
            if raw.get("expense_categories") is not None
            else None,
            built_events=tuple(
                CanonicalEventV2.model_validate(e) for e in raw.get("built_events") or ()
            ),
            pending_event=CanonicalEventV2.model_validate(raw["pending_event"])
            if raw.get("pending_event") is not None
            else None,
        )


class PendingDecompositionStore:
    """One pending decomposition per user, consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:pending_decomposition"

    async def set_pending(
        self,
        *,
        user_id: str,
        pending: PendingDecomposition,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        await self._redis.set_json(self._key(user_id), pending.to_dict(), ttl_seconds=ttl_seconds)

    async def pop_pending(self, *, user_id: str) -> PendingDecomposition | None:
        """Read the pending decomposition and clear it in the same call -- a
        stale or expired selection must never resurrect an old one."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw:
            return None
        await self._redis.set_json(key, {}, ttl_seconds=1)
        try:
            return PendingDecomposition.from_dict(raw)
        except Exception:  # noqa: BLE001 -- a shape from before a change, still
            # inside its 10-minute TTL across a deploy. Treated as absent
            # rather than raised, same reasoning as PlanStore.get_plan's
            # identical guard.
            return None

    async def clear(self, *, user_id: str) -> None:
        await self._redis.set_json(self._key(user_id), {}, ttl_seconds=1)
