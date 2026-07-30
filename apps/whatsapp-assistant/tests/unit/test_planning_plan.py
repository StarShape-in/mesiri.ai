"""Unit tests for planning/plan.py's dataclasses -- construction, dependency
extraction, and JSON round-tripping (the shape stored in Redis by
PlanStore)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.plan import DuplicateStepIdError, Plan, PlanOrigin, PlanStep, StepRef, StepStatus


def test_depends_on_is_empty_for_a_step_with_only_literal_fields():
    step = PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={"name": "Paraclette"})
    assert step.depends_on == frozenset()


def test_depends_on_collects_every_stepref_step_id():
    step = PlanStep(
        step_id="s4",
        workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
        fields={"project": StepRef("s1", "project_id"), "user": StepRef("s3", "user_id")},
    )
    assert step.depends_on == frozenset({"s1", "s3"})


def test_plan_rejects_duplicate_step_ids():
    dup = PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={})
    other = PlanStep(step_id="s1", workflow_key=WorkflowKey.CREATE_USER, fields={})
    with pytest.raises(DuplicateStepIdError):
        Plan(
            plan_id="plan_1",
            correlation_id="cor_1",
            user_id="usr_1",
            origin=PlanOrigin.DECOMPOSITION,
            steps=(dup, other),
        )


def test_plan_round_trips_through_to_dict_from_dict_including_steprefs():
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id="usr_1",
        origin=PlanOrigin.DECOMPOSITION,
        steps=(
            PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={"name": "Paraclette"}),
            PlanStep(
                step_id="s2",
                workflow_key=WorkflowKey.SITE_CREATE,
                fields={"name": "Tower B", "project": StepRef("s1", "project_id")},
                status=StepStatus.PENDING,
            ),
        ),
    )
    restored = Plan.from_dict(plan.to_dict())
    assert restored == plan
    # The StepRef survives the round trip as a StepRef, not a plain dict.
    assert isinstance(restored.steps[1].fields["project"], StepRef)
    assert restored.steps[1].fields["project"] == StepRef("s1", "project_id")


def test_plan_round_trip_preserves_outputs_and_status():
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id="usr_1",
        origin=PlanOrigin.RESOLUTION,
        steps=(
            PlanStep(
                step_id="s1",
                workflow_key=WorkflowKey.CREATE_USER,
                fields={"name": "Hysamm"},
                status=StepStatus.DONE,
                outputs={"user_id": "usr_abc123"},
            ),
        ),
    )
    restored = Plan.from_dict(plan.to_dict())
    assert restored.steps[0].status is StepStatus.DONE
    assert restored.steps[0].outputs == {"user_id": "usr_abc123"}


def test_plan_step_lookup_by_id():
    s1 = PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={})
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id="usr_1",
        origin=PlanOrigin.DECOMPOSITION,
        steps=(s1,),
    )
    assert plan.step("s1") is s1
    assert plan.step("missing") is None


def test_with_steps_returns_new_plan_leaving_original_untouched():
    s1 = PlanStep(step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={})
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id="usr_1",
        origin=PlanOrigin.DECOMPOSITION,
        steps=(s1,),
    )
    s1_done = PlanStep(
        step_id="s1", workflow_key=WorkflowKey.PROJECT_CREATE, fields={}, status=StepStatus.DONE
    )
    updated = plan.with_steps((s1_done,))
    assert plan.steps[0].status is StepStatus.PENDING
    assert updated.steps[0].status is StepStatus.DONE
