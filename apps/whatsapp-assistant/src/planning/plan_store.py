"""Redis-backed Plan store (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §6,
§10 Phase 1).

One Plan per user, holding N ordered PlanSteps. This is the store both
producers write into (Plan-layer doc §4.2/§4.4): a decomposed multi-intent
message starts with N>1 steps here; the entity-resolution layer's
continuation (docs/execution/ENTITY_RESOLUTION_PLAN.md §3.3) is the same
store holding N=1, with `insert_step` splicing in a step when a prerequisite
turns out to be Missing. There is exactly one store and one resume path so
"what happens when a planned step hits a missing entity" has one answer
instead of two.

Mirrors workflows/batch_store.py's PendingBatchStore shape (Redis-is-a-hint
posture, pop/advance discipline, per-user key) -- this store supersedes it
for anything with real dependency structure; PendingBatchStore itself is
untouched here (still used by the existing material->activity batch path
until that migrates, plan-layer doc §10 Phase 2/3 regression anchor).
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Protocol

from .plan import Plan, PlanOrigin, PlanStep, StepStatus

#: Same reasoning as PendingBatchStore's TTL: long enough for a multi-step
#: plan with a disambiguation round, short enough that a user who vanished
#: mid-plan doesn't leave a stale one alive forever. Flagged as an open
#: question in the plan-layer doc §12 -- a five-step plan may legitimately
#: outlive 30 minutes; revisit with real usage data before raising it blind.
_DEFAULT_TTL_SECONDS = 1800

_log = logging.getLogger(__name__)


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class PlanNotFoundError(ValueError):
    pass


class StepNotFoundError(ValueError):
    pass


def _transitive_dependents(plan: Plan, failed_step_id: str) -> set[str]:
    """Every step_id that depends on ``failed_step_id``, directly or through
    another cancelled step -- the set that gets CANCELLED, never attempted
    (plan-layer doc §7.4 / ADR-C4)."""
    cancelled = {failed_step_id}
    changed = True
    while changed:
        changed = False
        for step in plan.steps:
            if step.step_id in cancelled:
                continue
            if step.depends_on & cancelled:
                cancelled.add(step.step_id)
                changed = True
    cancelled.discard(failed_step_id)
    return cancelled


class PlanStore:
    """The one plan per user, and the operations both the decomposition
    producer and the entity-resolution producer perform on it."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:plan"

    async def start_plan(
        self, *, plan: Plan, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._redis.set_json(
            self._key(plan.user_id), plan.to_dict(), ttl_seconds=ttl_seconds
        )

    async def get_plan(self, *, user_id: str) -> Plan | None:
        raw = await self._redis.get_json(self._key(user_id))
        if not raw or not raw.get("steps"):
            return None
        try:
            return Plan.from_dict(raw)
        except Exception:  # noqa: BLE001 -- see below
            # A plan Redis still holds but this build can no longer read --
            # in practice one written before a shape change, still inside its
            # 30-minute TTL across a deploy. Treated as absent rather than
            # raised: the alternative is every message from that user failing
            # for half an hour over a follow-up offer, when the underlying
            # record (the project/user they created) was already saved and
            # the worst real consequence is one un-offered next step.
            _log.warning("plan_store.unreadable_plan user=%s", user_id, exc_info=True)
            return None

    async def has_pending(self, *, user_id: str) -> bool:
        return await self.get_plan(user_id=user_id) is not None

    async def next_runnable_step(self, *, user_id: str) -> PlanStep | None:
        """The first PENDING step whose dependencies are all DONE, in plan
        order. None when nothing is runnable -- either the plan is finished,
        or (should never happen given topological_order's guarantee) every
        remaining step is blocked."""
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            return None
        done_ids = {s.step_id for s in plan.steps if s.status is StepStatus.DONE}
        for step in plan.steps:
            if step.status is StepStatus.PENDING and step.depends_on <= done_ids:
                return step
        return None

    async def is_complete(self, *, user_id: str) -> bool:
        """True once every step has reached a terminal status (DONE, FAILED,
        or CANCELLED) -- the point at which a closing summary can be sent."""
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            return True
        terminal = {StepStatus.DONE, StepStatus.FAILED, StepStatus.CANCELLED}
        return all(s.status in terminal for s in plan.steps)

    async def _replace_step(
        self, *, user_id: str, step_id: str, updated: PlanStep
    ) -> Plan:
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            raise PlanNotFoundError(f"no active plan for user {user_id}")
        if plan.step(step_id) is None:
            raise StepNotFoundError(f"plan {plan.plan_id}: no step {step_id!r}")
        new_steps = tuple(updated if s.step_id == step_id else s for s in plan.steps)
        new_plan = plan.with_steps(new_steps)
        await self._redis.set_json(self._key(user_id), new_plan.to_dict(), ttl_seconds=_DEFAULT_TTL_SECONDS)
        return new_plan

    async def mark_step_running(self, *, user_id: str, step_id: str) -> Plan:
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            raise PlanNotFoundError(f"no active plan for user {user_id}")
        step = plan.step(step_id)
        if step is None:
            raise StepNotFoundError(f"plan {plan.plan_id}: no step {step_id!r}")
        # dataclasses.replace, not a field-by-field rebuild: every status
        # mutation here must carry the whole step forward untouched apart
        # from what it is changing. A rebuild silently drops any field added
        # to PlanStep later -- which is exactly how workflow_instance_id
        # would have been lost the moment a step was marked RUNNING.
        updated = dataclasses.replace(step, status=StepStatus.RUNNING)
        return await self._replace_step(user_id=user_id, step_id=step_id, updated=updated)

    async def mark_step_done(
        self, *, user_id: str, step_id: str, outputs: dict[str, str]
    ) -> Plan:
        """Record a step's success and the outputs it produced -- these feed
        every StepRef in a later step's fields that names this step_id."""
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            raise PlanNotFoundError(f"no active plan for user {user_id}")
        step = plan.step(step_id)
        if step is None:
            raise StepNotFoundError(f"plan {plan.plan_id}: no step {step_id!r}")
        updated = dataclasses.replace(step, status=StepStatus.DONE, outputs=dict(outputs))
        return await self._replace_step(user_id=user_id, step_id=step_id, updated=updated)

    async def mark_step_failed(self, *, user_id: str, step_id: str) -> Plan:
        """Record a step's failure and cancel every step that transitively
        depends on it, without attempting them (ADR-C4) -- a step with no
        dependency on the failed one still runs (plan-layer doc §7.4's
        Paraclette example: create-user has no dependency on create-project,
        so it still runs even if the project step fails)."""
        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            raise PlanNotFoundError(f"no active plan for user {user_id}")
        step = plan.step(step_id)
        if step is None:
            raise StepNotFoundError(f"plan {plan.plan_id}: no step {step_id!r}")

        to_cancel = _transitive_dependents(plan, step_id)

        def _apply(s: PlanStep) -> PlanStep:
            if s.step_id == step_id:
                return dataclasses.replace(s, status=StepStatus.FAILED)
            if s.step_id in to_cancel and s.status is StepStatus.PENDING:
                return dataclasses.replace(s, status=StepStatus.CANCELLED)
            return s

        new_plan = plan.with_steps(tuple(_apply(s) for s in plan.steps))
        await self._redis.set_json(
            self._key(user_id), new_plan.to_dict(), ttl_seconds=_DEFAULT_TTL_SECONDS
        )
        return new_plan

    async def insert_step(
        self, *, user_id: str, step: PlanStep, before_step_id: str
    ) -> Plan:
        """Splice ``step`` into the plan immediately before ``before_step_id``
        -- what the entity-resolution layer calls when a Missing entity is
        discovered while executing an in-progress plan
        (docs/execution/ENTITY_RESOLUTION_PLAN.md §3.3, plan-layer doc §4.4).
        The blocked step's own fields are the caller's responsibility to
        rewrite with a StepRef pointing at the new step's step_id -- this
        method only performs the list surgery and re-validates order.

        Raises via ordering.topological_order if the insertion produces an
        unresolvable or cyclic plan -- callers must import that function
        themselves to pre-validate before calling this, since raising deep
        inside store persistence would leave Redis in an inconsistent state.
        """
        from .ordering import topological_order  # local import: avoids a
        # store <-> ordering import cycle, since ordering.py has no reason
        # to depend on the store and shouldn't gain one for this.

        plan = await self.get_plan(user_id=user_id)
        if plan is None:
            raise PlanNotFoundError(f"no active plan for user {user_id}")
        if plan.step(before_step_id) is None:
            raise StepNotFoundError(f"plan {plan.plan_id}: no step {before_step_id!r}")

        insert_at = next(i for i, s in enumerate(plan.steps) if s.step_id == before_step_id)
        new_steps = list(plan.steps)
        new_steps.insert(insert_at, step)
        ordered = topological_order(new_steps)

        new_origin = (
            plan.origin if plan.origin is PlanOrigin.RESOLUTION else PlanOrigin.MIXED
        )
        # dataclasses.replace, for the same reason with_steps and the status
        # mutations use it: a field-by-field rebuild drops whatever was added
        # to Plan since it was written -- which is exactly how this line lost
        # organization_id/permissions the moment identity moved onto the plan.
        new_plan = dataclasses.replace(plan, origin=new_origin, steps=ordered)
        await self._redis.set_json(
            self._key(user_id), new_plan.to_dict(), ttl_seconds=_DEFAULT_TTL_SECONDS
        )
        return new_plan

    async def clear(self, *, user_id: str) -> None:
        # No delete primitive on the M1 client/fake -- overwrite with an
        # immediately-expired marker, same trick as batch_store.py's clear.
        await self._redis.set_json(self._key(user_id), {}, ttl_seconds=1)
