"""Redis-backed pending decomposition (short-lived, pop-once).

docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §14: "the single-message
material/project/site/stock gates never re-run per decomposed segment."
This closes the project/site half of that gap.

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

Explicitly NOT covering the material-unit/stock gates (an ambiguous catalog
name, an over-stock usage report) -- those are genuinely per-segment and a
narrower slice of real traffic; scoped out on purpose, named in the design
doc's risk table rather than silently absent.
"""

from __future__ import annotations

from typing import Any, Protocol

from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

_DEFAULT_TTL_SECONDS = 600  # 10 minutes -- matches PendingReportStore's own reasoning


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class PendingDecomposition:
    """What is held while a project/site picker is answered: the segment
    texts already produced by decompose() (never re-decomposed on resume --
    a second call would risk a different split for the same message), the
    resolved context AT THE TIME OF HOLDING (so a second gate, e.g. site
    after project, sees the just-picked project_id already applied), and
    the expense category list the per-segment extraction calls need."""

    __slots__ = ("segments", "resolved", "expense_categories")

    def __init__(
        self,
        *,
        segments: tuple[str, ...],
        resolved: ResolvedContextV2,
        expense_categories: tuple[str, ...] | None,
    ) -> None:
        self.segments = segments
        self.resolved = resolved
        self.expense_categories = expense_categories

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": list(self.segments),
            "resolved": self.resolved.model_dump(mode="json"),
            "expense_categories": list(self.expense_categories)
            if self.expense_categories is not None
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
