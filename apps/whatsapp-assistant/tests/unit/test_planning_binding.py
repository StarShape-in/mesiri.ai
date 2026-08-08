"""Unit tests for planning/binding.py -- just-in-time ref resolution and
CanonicalEventV2 construction (ADR-C2, plan-layer doc §7.2 / §11.1).

These cover the two gaps Phase 1 shipped with:
  (a) a step must be able to rebuild a COMPLETE event, including the parts
      that are not derivable from workflow_key and the parts that live on
      the plan rather than the step;
  (b) a ref's destination must be honoured -- a project reference has to
      land on the event's project_id, never in fields, or site_create
      ignores it and asks "which project?" all over again.
"""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from planning.binding import UnresolvedStepRefError, build_event, resolve_step
from planning.plan import Plan, PlanOrigin, PlanStep, StepRef, StepStatus

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"


def _plan(*steps: PlanStep) -> Plan:
    return Plan(
        plan_id="plan_1",
        correlation_id="cor_1",
        user_id=USR,
        organization_id=ORG,
        origin=PlanOrigin.DECOMPOSITION,
        source_message_id="msg_1",
        conversation_id="conv_1",
        permissions=("projects:write", "sites:write"),
        steps=steps,
    )


def _done_project_step() -> PlanStep:
    return PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={"name": "Paraclette"},
        status=StepStatus.DONE,
        outputs={"project_id": PRJ},
    )


def _site_step() -> PlanStep:
    return PlanStep(
        step_id="s2",
        workflow_key=WorkflowKey.SITE_CREATE,
        event_type=CanonicalEventType.SITE_CREATE_REQUESTED,
        fields={"name": "Tower B"},
        scope={"project_id": StepRef("s1", "project_id")},
    )


def test_scope_ref_lands_on_project_id_not_in_fields():
    """The whole point of §11.1(b). site_create/nodes.py reads
    state["project_id"] and explicitly never collected_fields -- a project
    that arrived in fields would be silently ignored."""
    plan = _plan(_done_project_step(), _site_step())
    event = build_event(_site_step(), plan)

    assert event.project_id == PRJ
    assert "project_id" not in event.fields
    assert event.fields == {"name": "Tower B"}


def test_build_event_carries_plan_level_identity():
    """§11.1(a): organization_id, permissions and conversation_id live on
    the plan, and a step that could not reach them produced an event missing
    exactly the fields nothing downstream could recover."""
    plan = _plan(_done_project_step(), _site_step())
    event = build_event(_site_step(), plan)

    assert event.organization_id == ORG
    assert event.user_id == USR
    assert event.permissions == ["projects:write", "sites:write"]
    assert event.conversation_id == "conv_1"
    assert event.source_message_id == "msg_1"
    assert event.completeness is IntentCompleteness.ACTIONABLE


def test_event_type_comes_from_the_step_not_the_workflow_key():
    """workflow_key -> event_type is many-to-one, so it cannot be derived.
    SITE_UPDATE is reachable from two different event types; the step must
    say which one it is."""
    continuation = PlanStep(
        step_id="s5",
        workflow_key=WorkflowKey.SITE_UPDATE,
        event_type=CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED,
        fields={"narrative": "slab work started"},
    )
    plan = _plan(continuation)
    event = build_event(continuation, plan)
    assert event.event_type is CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED

    fresh = PlanStep(
        step_id="s6",
        workflow_key=WorkflowKey.SITE_UPDATE,
        event_type=CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED,
        fields={"narrative": "slab work started"},
    )
    assert build_event(fresh, _plan(fresh)).event_type is (
        CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED
    )


def test_field_refs_resolve_from_a_completed_steps_outputs():
    user_done = PlanStep(
        step_id="s3",
        workflow_key=WorkflowKey.CREATE_USER,
        event_type=CanonicalEventType.CREATE_USER_REQUESTED,
        fields={"full_name": "Hysamm"},
        status=StepStatus.DONE,
        outputs={"user_id": "usr_1", "full_name": "Hisham"},
    )
    member = PlanStep(
        step_id="s4",
        workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
        event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        fields={"member_name": StepRef("s3", "full_name"), "role": "PROJECT_MANAGER"},
        scope={"project_id": StepRef("s1", "project_id")},
    )
    plan = _plan(_done_project_step(), user_done, member)
    event = build_event(member, plan)

    # The name the user was ACTUALLY created under, not the original hint.
    assert event.fields["member_name"] == "Hisham"
    assert event.fields["role"] == "PROJECT_MANAGER"
    assert event.project_id == PRJ


def test_literal_scope_passes_through_unchanged():
    step = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.SITE_CREATE,
        event_type=CanonicalEventType.SITE_CREATE_REQUESTED,
        fields={"name": "Tower B"},
        scope={"project_id": PRJ},
    )
    assert build_event(step, _plan(step)).project_id == PRJ


def test_unresolved_ref_raises_rather_than_silently_becoming_none():
    """A None project_id would write a record against no project at all.
    Failing loudly is the whole point -- this is a producer/consumer
    contract bug, not a user-facing state."""
    project_done_without_publishing = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={"name": "Paraclette"},
        status=StepStatus.DONE,
        outputs={},  # published nothing
    )
    plan = _plan(project_done_without_publishing, _site_step())
    with pytest.raises(UnresolvedStepRefError):
        build_event(_site_step(), plan)


def test_ref_to_a_step_that_has_not_run_raises():
    pending_project = PlanStep(
        step_id="s1",
        workflow_key=WorkflowKey.PROJECT_CREATE,
        event_type=CanonicalEventType.PROJECT_CREATE_REQUESTED,
        fields={"name": "Paraclette"},
    )
    plan = _plan(pending_project, _site_step())
    with pytest.raises(UnresolvedStepRefError):
        build_event(_site_step(), plan)


def test_resolve_step_is_pure_and_leaves_the_step_untouched():
    plan = _plan(_done_project_step(), _site_step())
    step = _site_step()
    fields, scope = resolve_step(step, plan)

    assert scope == {"project_id": PRJ}
    assert fields == {"name": "Tower B"}
    # The step itself still carries the unresolved ref.
    assert isinstance(step.scope["project_id"], StepRef)


def test_correlation_id_defaults_to_the_plans_so_steps_group_as_one_interaction():
    plan = _plan(_done_project_step(), _site_step())
    assert build_event(_site_step(), plan).correlation_id == "cor_1"
    assert build_event(_site_step(), plan, correlation_id="other").correlation_id == "other"
