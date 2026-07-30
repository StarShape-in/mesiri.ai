"""Unit tests for PlanStore -- in-memory fake Redis, mirrors
test_batch_store.py's pattern.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.plan import Plan, PlanOrigin, PlanStep, StepRef, StepStatus
from planning.plan_store import PlanNotFoundError, PlanStore, StepNotFoundError

USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


def _paraclette_plan() -> Plan:
    return Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        origin=PlanOrigin.DECOMPOSITION,
        steps=(
            PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={"name": "Paraclette"}),
            PlanStep(
                step_id="s2",
                workflow_key=WorkflowKey.SITE_CREATE,
                fields={"name": "Tower B", "project": StepRef("s1", "project_id")},
            ),
            PlanStep(step_id="s3", workflow_key=WorkflowKey.CREATE_USER, fields={"name": "Hysamm"}),
        ),
    )


async def test_get_plan_returns_none_when_never_started():
    store = PlanStore(_FakeRedis())
    assert await store.get_plan(user_id=USR) is None
    assert await store.has_pending(user_id=USR) is False


async def test_start_plan_then_get_plan_round_trips():
    store = PlanStore(_FakeRedis())
    plan = _paraclette_plan()
    await store.start_plan(plan=plan)
    fetched = await store.get_plan(user_id=USR)
    assert fetched == plan


async def test_next_runnable_step_is_first_step_with_no_pending_deps():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    step = await store.next_runnable_step(user_id=USR)
    assert step is not None
    # s2 depends on s1 (not yet DONE); s3 has no deps -- but s1 is first in
    # plan order and has no deps either, so s1 runs first.
    assert step.step_id == "s1"


async def test_next_runnable_step_skips_a_step_whose_dependency_is_not_done_yet():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    await store.mark_step_running(user_id=USR, step_id="s1")
    # s1 is RUNNING, not DONE -- s2 (depends on s1) must not be offered yet,
    # so the next runnable step should be s3 (no dependency at all).
    step = await store.next_runnable_step(user_id=USR)
    assert step is not None
    assert step.step_id == "s3"


async def test_mark_step_done_unblocks_its_dependent():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    await store.mark_step_done(user_id=USR, step_id="s1", outputs={"project_id": "proj_abc"})

    step = await store.next_runnable_step(user_id=USR)
    assert step is not None
    assert step.step_id in ("s2", "s3")  # both now eligible; s2 since s1 is DONE

    plan = await store.get_plan(user_id=USR)
    s1 = plan.step("s1")
    assert s1.status is StepStatus.DONE
    assert s1.outputs == {"project_id": "proj_abc"}


async def test_mark_step_failed_cancels_transitive_dependents_but_not_independent_steps():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    plan = await store.mark_step_failed(user_id=USR, step_id="s1")

    assert plan.step("s1").status is StepStatus.FAILED
    assert plan.step("s2").status is StepStatus.CANCELLED  # depends on s1
    assert plan.step("s3").status is StepStatus.PENDING  # independent -- still runnable


async def test_is_complete_false_while_any_step_pending_true_once_all_terminal():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    assert await store.is_complete(user_id=USR) is False

    await store.mark_step_failed(user_id=USR, step_id="s1")  # fails s1, cancels s2
    assert await store.is_complete(user_id=USR) is False  # s3 still pending

    await store.mark_step_done(user_id=USR, step_id="s3", outputs={})
    assert await store.is_complete(user_id=USR) is True


async def test_insert_step_splices_a_resolution_step_ahead_of_the_blocked_one():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())

    # s3 (CREATE_USER) blocked because "Hysamm" didn't resolve -- but here we
    # simulate inserting a disambiguation/creation step ahead of ADD_PROJECT_
    # MEMBER-shaped s2 to exercise the splice, since the fixture's s2 depends
    # on s1 already. Insert an unrelated no-dependency step before s2.
    new_step = PlanStep(step_id="s_new", workflow_key=WorkflowKey.CREATE_USER, fields={"name": "Hysamm"})
    plan = await store.insert_step(user_id=USR, step=new_step, before_step_id="s2")

    order = [s.step_id for s in plan.steps]
    assert "s_new" in order
    assert order.index("s_new") < order.index("s2")
    assert plan.origin.value == "mixed"


async def test_mark_step_running_on_missing_plan_raises_plan_not_found():
    store = PlanStore(_FakeRedis())
    try:
        await store.mark_step_running(user_id=USR, step_id="s1")
        assert False, "expected PlanNotFoundError"
    except PlanNotFoundError:
        pass


async def test_mark_step_done_on_unknown_step_raises_step_not_found():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    try:
        await store.mark_step_done(user_id=USR, step_id="does-not-exist", outputs={})
        assert False, "expected StepNotFoundError"
    except StepNotFoundError:
        pass


async def test_clear_empties_the_plan():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    assert await store.has_pending(user_id=USR) is True

    await store.clear(user_id=USR)
    assert await store.has_pending(user_id=USR) is False


async def test_plans_are_scoped_per_user():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    assert await store.has_pending(user_id="usr_other") is False
    assert await store.has_pending(user_id=USR) is True
