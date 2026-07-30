"""Unit tests for PlanStore -- in-memory fake Redis, mirrors
test_batch_store.py's pattern.
"""

from __future__ import annotations

from typing import Any

import pytest

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.plan import Plan, PlanOrigin, PlanStep, StepRef, StepStatus
from planning.plan_store import PlanNotFoundError, PlanStore, StepNotFoundError

USR = "22222222-2222-4222-8222-222222222222"
ORG = "11111111-1111-4111-8111-111111111111"


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
    """Three steps: create the project, create a site under it (scope ref),
    and create a user (independent of both)."""
    return Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=PlanOrigin.DECOMPOSITION,
        source_message_id="msg_1",
        steps=(
            PlanStep(
                step_id="s1",
                workflow_key=WorkflowKey.PROJECT_CREATE,
                event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
                fields={"name": "Paraclette"},
            ),
            PlanStep(
                step_id="s2",
                workflow_key=WorkflowKey.SITE_CREATE,
                event_type=CanonicalEventType.SITE_CREATE_REQUESTED,
                fields={"name": "Tower B"},
                scope={"project_id": StepRef("s1", "project_id")},
            ),
            PlanStep(
                step_id="s3",
                workflow_key=WorkflowKey.CREATE_USER,
                event_type=CanonicalEventType.CREATE_USER_REQUESTED,
                fields={"full_name": "Hysamm"},
            ),
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
    new_step = PlanStep(
        step_id="s_new",
        workflow_key=WorkflowKey.CREATE_USER,
        event_type=CanonicalEventType.CREATE_USER_REQUESTED,
        fields={"full_name": "Hysamm"},
    )
    plan = await store.insert_step(user_id=USR, step=new_step, before_step_id="s2")

    order = [s.step_id for s in plan.steps]
    assert "s_new" in order
    assert order.index("s_new") < order.index("s2")
    assert plan.origin.value == "mixed"


async def test_mark_step_running_on_missing_plan_raises_plan_not_found():
    store = PlanStore(_FakeRedis())
    with pytest.raises(PlanNotFoundError):
        await store.mark_step_running(user_id=USR, step_id="s1")


async def test_mark_step_done_on_unknown_step_raises_step_not_found():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    with pytest.raises(StepNotFoundError):
        await store.mark_step_done(user_id=USR, step_id="does-not-exist", outputs={})


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


async def test_remove_step_drops_only_the_named_step_when_nothing_depends_on_it():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())

    plan = await store.remove_step(user_id=USR, step_id="s3")

    assert plan is not None
    assert [s.step_id for s in plan.steps] == ["s1", "s2"]


async def test_remove_step_cascades_to_transitive_dependents():
    """Removing the project must also drop the site under it -- its scope
    references the project's own output, so it cannot run without it."""
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())

    plan = await store.remove_step(user_id=USR, step_id="s1")

    assert plan is not None
    assert [s.step_id for s in plan.steps] == ["s3"]  # independent -- kept


async def test_removed_steps_are_deleted_not_cancelled():
    """Unlike mark_step_failed, there is no execution outcome to report --
    the user removed this before it was ever attempted, so it must not
    appear at all, not even as CANCELLED."""
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())

    plan = await store.remove_step(user_id=USR, step_id="s1")

    assert plan.step("s1") is None
    assert plan.step("s2") is None


async def test_removing_every_step_clears_the_plan_entirely():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())

    # s1 cascades to s2; then remove the only step left.
    await store.remove_step(user_id=USR, step_id="s1")
    plan = await store.remove_step(user_id=USR, step_id="s3")

    assert plan is None
    assert await store.get_plan(user_id=USR) is None


async def test_remove_step_on_missing_plan_raises_plan_not_found():
    store = PlanStore(_FakeRedis())
    with pytest.raises(PlanNotFoundError):
        await store.remove_step(user_id=USR, step_id="s1")


async def test_remove_step_on_unknown_step_id_raises_step_not_found():
    store = PlanStore(_FakeRedis())
    await store.start_plan(plan=_paraclette_plan())
    with pytest.raises(StepNotFoundError):
        await store.remove_step(user_id=USR, step_id="does-not-exist")
