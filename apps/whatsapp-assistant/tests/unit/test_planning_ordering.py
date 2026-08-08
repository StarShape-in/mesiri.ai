"""Unit tests for planning/ordering.py -- pure, no Redis, no LLM.

Uses the Paraclette message's five steps (docs/execution/
COMPOSITE_REQUEST_PLAN_LAYER.md §1) as the running fixture, since it is the
scenario that motivated this layer.
"""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.ordering import PlanCycleError, PlanUnresolvedRefError, topological_order
from planning.plan import PlanStep, StepRef

#: Ordering is indifferent to event_type -- it reads only StepRefs -- so
#: these tests use one placeholder rather than a realistic per-key mapping.
_ANY = CanonicalEventType.PROJECT_CREATE_REQUESTED


def _step(step_id: str, workflow_key: WorkflowKey, *, scope=None, **fields) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        workflow_key=workflow_key,
        event_type=_ANY,
        fields=fields,
        scope=scope or {},
    )


def test_single_step_plan_orders_trivially():
    steps = [_step("s1", WorkflowKey.PROJECT_CREATE, name="Paraclette")]
    assert topological_order(steps) == tuple(steps)


def test_independent_steps_keep_original_relative_order():
    s1 = _step("s1", WorkflowKey.PROJECT_CREATE, name="Paraclette")
    s2 = _step("s2", WorkflowKey.CREATE_USER, name="Hysamm")
    # Neither references the other -- both eligible in the first pass.
    assert topological_order([s2, s1]) == (s2, s1)


def test_dependent_step_moves_after_its_dependency_even_if_authored_first():
    site = _step(
        "s2",
        WorkflowKey.SITE_CREATE,
        name="Tower B",
        scope={"project_id": StepRef("s1", "project_id")},
    )
    project = _step("s1", WorkflowKey.PROJECT_CREATE, name="Paraclette")
    # site authored before project in the input list -- must still come after.
    ordered = topological_order([site, project])
    assert [s.step_id for s in ordered] == ["s1", "s2"]


def test_depends_on_sees_refs_in_scope_not_just_fields():
    """The project a site belongs to is scope, not a collected field -- a
    dependency expressed only through scope must still order correctly."""
    site = _step(
        "s2", WorkflowKey.SITE_CREATE, name="Tower B",
        scope={"project_id": StepRef("s1", "project_id")},
    )
    assert site.depends_on == frozenset({"s1"})


def test_full_paraclette_plan_orders_correctly():
    project = _step("s1", WorkflowKey.PROJECT_CREATE, name="Paraclette")
    site = _step(
        "s2", WorkflowKey.SITE_CREATE, name="Tower B",
        scope={"project_id": StepRef("s1", "project_id")},
    )
    user = _step("s3", WorkflowKey.CREATE_USER, name="Hysamm", phone="+919847656072")
    member = _step(
        "s4",
        WorkflowKey.ADD_PROJECT_MEMBER,
        member_name=StepRef("s3", "full_name"),
        role="PROJECT_MANAGER",
        scope={"project_id": StepRef("s1", "project_id")},
    )
    activity = _step(
        "s5",
        WorkflowKey.SITE_UPDATE,
        narrative="slab work started",
        scope={
            "project_id": StepRef("s1", "project_id"),
            "site_id": StepRef("s2", "site_id"),
        },
    )
    # Authored out of dependency order on purpose.
    ordered = topological_order([activity, member, user, site, project])
    order = [s.step_id for s in ordered]

    assert order.index("s1") < order.index("s2")  # project before site
    assert order.index("s1") < order.index("s4")  # project before membership
    assert order.index("s3") < order.index("s4")  # user before membership
    assert order.index("s1") < order.index("s5")  # project before activity
    assert order.index("s2") < order.index("s5")  # site before activity
    assert set(order) == {"s1", "s2", "s3", "s4", "s5"}


def test_ref_to_a_step_not_in_the_plan_raises_unresolved_ref():
    orphan = _step("s2", WorkflowKey.SITE_CREATE, project=StepRef("s1", "project_id"))
    with pytest.raises(PlanUnresolvedRefError):
        topological_order([orphan])


def test_two_step_cycle_raises_plan_cycle_error():
    a = _step("a", WorkflowKey.SITE_CREATE, project=StepRef("b", "x"))
    b = _step("b", WorkflowKey.PROJECT_CREATE, name=StepRef("a", "y"))
    with pytest.raises(PlanCycleError):
        topological_order([a, b])


def test_self_reference_raises_plan_cycle_error():
    a = _step("a", WorkflowKey.SITE_CREATE, project=StepRef("a", "x"))
    with pytest.raises(PlanCycleError):
        topological_order([a])
