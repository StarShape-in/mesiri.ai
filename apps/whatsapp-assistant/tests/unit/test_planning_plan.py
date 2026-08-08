"""Unit tests for planning/plan.py's dataclasses -- construction, dependency
extraction, the fields/scope split, and JSON round-tripping (the shape
stored in Redis by PlanStore)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.plan import (
    DuplicateStepIdError,
    InvalidScopeKeyError,
    Plan,
    PlanOrigin,
    PlanStep,
    StepRef,
    StepStatus,
)

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _plan(*steps: PlanStep, origin: PlanOrigin = PlanOrigin.DECOMPOSITION) -> Plan:
    return Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=origin,
        steps=steps,
    )


def test_depends_on_is_empty_for_a_step_with_only_literal_fields():
    step = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={"name": "Paraclette"},
    )
    assert step.depends_on == frozenset()


def test_depends_on_collects_step_ids_from_both_fields_and_scope():
    step = PlanStep(
        step_id="s4",
        workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
        event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        fields={"member_name": StepRef("s3", "full_name")},
        scope={"project_id": StepRef("s1", "project_id")},
    )
    assert step.depends_on == frozenset({"s1", "s3"})


def test_scope_rejects_a_key_that_is_not_project_or_site():
    """A collected value put in scope would be silently unapplied --
    CanonicalEventV2 is extra="forbid" and has nowhere to put it."""
    with pytest.raises(InvalidScopeKeyError):
        PlanStep(
            step_id="s1",
            workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
            event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
            fields={},
            scope={"member_name": "Hysam"},
        )


def test_plan_rejects_duplicate_step_ids():
    dup = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={},
    )
    other = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.CREATE_USER,
        event_type=CanonicalEventType.CREATE_USER_REQUESTED,
        fields={},
    )
    with pytest.raises(DuplicateStepIdError):
        _plan(dup, other)


def test_plan_round_trips_through_to_dict_from_dict_including_steprefs_in_scope():
    plan = _plan(
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
    )
    restored = Plan.from_dict(plan.to_dict())
    assert restored == plan
    # The StepRef survives as a StepRef, in scope, not as a plain dict.
    assert isinstance(restored.steps[1].scope["project_id"], StepRef)
    assert restored.steps[1].scope["project_id"] == StepRef("s1", "project_id")


def test_plan_round_trip_preserves_identity_outputs_and_status():
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=PlanOrigin.RESOLUTION,
        source_message_id="msg_1",
        conversation_id="conv_1",
        permissions=("projects:write",),
        steps=(
            PlanStep(
                step_id="s1",
                workflow_key=WorkflowKey.CREATE_USER,
                event_type=CanonicalEventType.CREATE_USER_REQUESTED,
                fields={"full_name": "Hysamm"},
                status=StepStatus.DONE,
                outputs={"user_id": "usr_abc123"},
                workflow_instance_id="wf_1",
            ),
        ),
    )
    restored = Plan.from_dict(plan.to_dict())
    assert restored == plan
    assert restored.organization_id == ORG
    assert restored.permissions == ("projects:write",)
    assert restored.conversation_id == "conv_1"
    assert restored.steps[0].outputs == {"user_id": "usr_abc123"}
    assert restored.steps[0].workflow_instance_id == "wf_1"


def test_plan_step_lookup_by_id():
    s1 = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={},
    )
    plan = _plan(s1)
    assert plan.step("s1") is s1
    assert plan.step("missing") is None


def test_with_steps_preserves_identity_fields():
    """dataclasses.replace, not a rebuild -- a field-by-field copy is how
    organization_id/permissions would silently vanish on the first
    mark_step_done."""
    s1 = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={},
    )
    plan = Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=PlanOrigin.DECOMPOSITION,
        permissions=("projects:write",),
        steps=(s1,),
    )
    updated = plan.with_steps(
        (
            PlanStep(
                step_id="s1",
                workflow_key=WorkflowKey.PROJECT_CREATE,
                event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
                fields={},
                status=StepStatus.DONE,
            ),
        )
    )
    assert plan.steps[0].status is StepStatus.PENDING
    assert updated.steps[0].status is StepStatus.DONE
    assert updated.organization_id == ORG
    assert updated.permissions == ("projects:write",)
