"""Redis-backed pending BATCH queue (#1 Multi-Activity).

One message can describe several distinct things ("Completed plastering in
Block A, started painting in Block B, repaired two columns"). WhatsApp
confirmation is inherently sequential -- a user can only tap one YES at a
time -- so this does NOT relax the single-active-workflow invariant
(workflows/runtime.py's partial unique index stays exactly as strict as
before: still at most one AWAITING_CONFIRMATION instance per user, ever).
Instead, the FIRST segment starts a normal workflow exactly as today: the
rest queue here and are started ONE AT A TIME, automatically, each time the
previous segment's confirmation resolves (see workflows/batch.py's
try_advance).

Mirrors interactions/pending_report.py's store/pop-once pattern, generalized
to a list consumed one element at a time rather than the whole thing at
once.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:pending_batch
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2

_DEFAULT_TTL_SECONDS = 1800  # 30 minutes -- a multi-segment report may take a few confirm/reject rounds


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


@dataclass(frozen=True, slots=True)
class BatchProgress:
    """Where a user is in their multi-segment batch, for prompt captioning
    ("(2 of 3)") and the final summary line."""

    #: 1-based index of the segment about to run (or that just ran).
    index: int
    #: Total segments in the ORIGINAL batch (constant across the batch's life).
    total: int
    #: One short line per already-resolved segment, in order -- e.g.
    #: "1. Material usage: recorded", "2. Activity update: couldn't record
    #: (no open activity)". Built up as the batch advances so the FINAL
    #: segment's reply can summarize the whole thing, not just itself.
    outcomes: tuple[str, ...]


class PendingBatchStore:
    """Stores the REMAINING queued segments (as CanonicalEventV2) plus
    BatchProgress bookkeeping, per user. Consumed one segment at a time via
    pop_next(); the batch is complete once pop_next() returns None."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:pending_batch"

    async def start_batch(
        self,
        *,
        user_id: str,
        remaining: list[CanonicalEventV2],
        total: int,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        """Queue the segments AFTER the first (which the caller already
        started through the normal single-workflow path, exactly as it
        would for a single-segment message). Only ever called when there IS
        a remainder -- a batch of size 1 never touches this store at all,
        so single-segment messages (the overwhelming majority) pay zero
        Redis cost for this feature."""
        await self._redis.set_json(
            self._key(user_id),
            {
                "remaining": [e.model_dump(mode="json") for e in remaining],
                "total": total,
                "outcomes": [],
            },
            ttl_seconds=ttl_seconds,
        )

    async def pop_next(
        self, *, user_id: str
    ) -> tuple[CanonicalEventV2, BatchProgress] | None:
        """Pop the next queued segment and its progress snapshot. None when
        the batch is empty or was never started -- the caller's loop
        terminates naturally on this, no separate "is batch active" check
        needed."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw or not raw.get("remaining"):
            return None

        remaining = list(raw["remaining"])
        next_raw = remaining.pop(0)
        total = int(raw.get("total", 1))
        outcomes = tuple(raw.get("outcomes", ()))
        index = total - len(remaining)  # 1-based position of the segment we're about to run

        await self._redis.set_json(
            key,
            {"remaining": remaining, "total": total, "outcomes": list(outcomes)},
            ttl_seconds=_DEFAULT_TTL_SECONDS,
        )
        return CanonicalEventV2.model_validate(next_raw), BatchProgress(
            index=index, total=total, outcomes=outcomes
        )

    async def record_outcome(self, *, user_id: str, outcome: str) -> None:
        """Append one segment's one-line result to the running log --
        called after EVERY segment resolves (including the last), so the
        final reply can list the whole batch's outcome, not just its own.
        Numbers the line itself (``"{index}. {outcome}"``) so every caller
        passes a plain description and numbering can never drift from the
        order segments actually resolved in."""
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw:
            return
        outcomes = list(raw.get("outcomes", ()))
        outcomes.append(f"{len(outcomes) + 1}. {outcome}")
        await self._redis.set_json(
            key,
            {"remaining": raw.get("remaining", []), "total": raw.get("total", 1), "outcomes": outcomes},
            ttl_seconds=_DEFAULT_TTL_SECONDS,
        )

    async def get_outcomes(self, *, user_id: str) -> tuple[str, ...]:
        raw = await self._redis.get_json(self._key(user_id))
        if not raw:
            return ()
        return tuple(raw.get("outcomes", ()))

    async def clear(self, *, user_id: str) -> None:
        # No delete primitive on the M1 client/fake -- overwrite with an
        # immediately-expired marker, same trick as active_context.py's
        # clear_active_context.
        await self._redis.set_json(self._key(user_id), {}, ttl_seconds=1)

    async def has_pending(self, *, user_id: str) -> bool:
        raw = await self._redis.get_json(self._key(user_id))
        return bool(raw and raw.get("remaining"))
