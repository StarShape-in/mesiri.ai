"""Unit tests for planning/decomposition.py -- the entity-linking rule that
turns N independently-extracted segments into one ordered Plan
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9, §7.2).

Fixtures are hand-built CanonicalEventV2 objects, exactly as if each had come
from canonicalization.build_canonical_event run once per
DecompositionResult.segments[i] -- this module is pure and never calls
extraction or canonicalization itself.
"""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from planning.decomposition import build_plan_from_segments
from planning.plan import PlanOrigin, StepRef

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"


def _event(event_type: CanonicalEventType, *, project_id=None, site_id=None, **fields) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id=f"evt_{event_type.value}",
        correlation_id="cor_starship",
        source_message_id="msg_starship",
        conversation_id="conv_1",
        event_type=event_type,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        permissions=["projects:write", "sites:write", "users:write"],
        fields=fields,
    )


def test_empty_input_produces_no_plan():
    result = build_plan_from_segments([], plan_id="plan_1")
    assert result.plan is None
    assert result.skipped == ()


def test_single_segment_still_produces_a_one_step_plan():
    events = [_event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Starship")]
    result = build_plan_from_segments(events, plan_id="plan_1")
    assert result.plan is not None
    assert len(result.plan.steps) == 1
    assert result.plan.steps[0].fields == {"name": "Starship"}


def test_site_step_binds_to_the_just_created_project_via_step_ref():
    """The Starship message: "create a project called Starship and then a
    site called Site A" -- the site segment's own extraction names no
    project at all (it said "it"), so the link must be inferred."""
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Starship"),
        _event(CanonicalEventType.SITE_CREATE_REQUESTED, name="Site A"),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    plan = result.plan
    assert plan is not None
    site_step = plan.step("s2")
    assert site_step.scope["project_id"] == StepRef("s1", "project_id")
    assert "project_id" not in site_step.fields  # never leaks into fields


def test_site_step_keeps_its_own_project_when_already_resolved():
    """If context resolution already pinned a real project (the sender
    named an EXISTING project, or has exactly one), that literal value must
    win over any inferred link -- there is nothing to bind."""
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Starship"),
        _event(CanonicalEventType.SITE_CREATE_REQUESTED, name="Site A", project_id=PRJ),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    site_step = result.plan.step("s2")
    assert site_step.scope["project_id"] == PRJ  # literal, not a StepRef


def test_activity_step_binds_to_both_project_and_site():
    """The full Paraclette chain's last step: an activity update requires
    BOTH project and site, and neither was named in that segment's own
    text ("log an activity that slab work started")."""
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Paraclette"),
        _event(CanonicalEventType.SITE_CREATE_REQUESTED, name="Tower B"),
        _event(
            CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED,
            narrative="slab work started",
        ),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    activity_step = result.plan.step("s3")
    assert activity_step.scope["project_id"] == StepRef("s1", "project_id")
    assert activity_step.scope["site_id"] == StepRef("s2", "site_id")


def test_add_member_binds_member_name_when_the_segment_named_nobody():
    """"create a new user named Hysamm... then make him project manager" --
    the second segment's own extraction gets role=PROJECT_MANAGER but no
    member_name at all (a bare pronoun)."""
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Paraclette"),
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
        _event(
            CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
            role="PROJECT_MANAGER",
            project_id=PRJ,
        ),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    member_step = result.plan.step("s3")
    assert member_step.fields["member_name"] == StepRef("s2", "full_name")
    assert member_step.fields["role"] == "PROJECT_MANAGER"


def test_add_member_binds_when_the_named_person_matches_the_just_created_user():
    """"add Hysamm as PM" -- this time the name IS extracted, and it matches
    (case/whitespace-insensitively) the user just created two segments
    earlier."""
    events = [
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
        _event(
            CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
            member_name="  hysamm ",
            role="PROJECT_MANAGER",
            project_id=PRJ,
        ),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    member_step = result.plan.step("s2")
    assert member_step.fields["member_name"] == StepRef("s1", "full_name")


def test_add_member_does_not_bind_when_the_named_person_is_someone_else():
    """"add Rajesh as PM" after creating Hysamm -- Rajesh is presumably an
    existing user; this module must not guess they mean the person just
    created. Left as a literal name for the entity-resolution layer to
    handle at execution time."""
    events = [
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
        _event(
            CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
            member_name="Rajesh",
            role="PROJECT_MANAGER",
            project_id=PRJ,
        ),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    member_step = result.plan.step("s2")
    assert member_step.fields["member_name"] == "Rajesh"


def test_unsupported_event_type_is_skipped_but_other_segments_still_plan():
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Starship"),
        _event(CanonicalEventType.CLARIFICATION_REQUIRED),
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    assert result.plan is not None
    assert len(result.plan.steps) == 2
    assert len(result.skipped) == 1
    assert result.skipped[0].index == 1
    assert result.skipped[0].reason == "unsupported_event_type"


def test_all_segments_unsupported_produces_no_plan():
    events = [_event(CanonicalEventType.CLARIFICATION_REQUIRED)]
    result = build_plan_from_segments(events, plan_id="plan_1")
    assert result.plan is None
    assert len(result.skipped) == 1


def test_plan_identity_comes_from_the_first_segment():
    events = [
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Starship"),
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
    ]
    result = build_plan_from_segments(events, plan_id="plan_starship")
    plan = result.plan
    assert plan.plan_id == "plan_starship"
    assert plan.correlation_id == "cor_starship"
    assert plan.organization_id == ORG
    assert plan.user_id == USR
    assert plan.source_message_id == "msg_starship"
    assert plan.conversation_id == "conv_1"
    assert plan.permissions == ("projects:write", "sites:write", "users:write")
    assert plan.origin is PlanOrigin.DECOMPOSITION


def test_two_independent_steps_preserve_authored_order():
    """Linking only ever looks BACKWARD (§ module docstring: "most recent
    EARLIER step") -- a segment can never bind to one stated after it, since
    the decomposer is asked never to reorder and a real sender never refers
    to something they haven't said yet. Two steps with no ref between them
    at all must still come out in the order they were authored (ordering.py's
    stability guarantee), proving topological_order runs but does nothing
    harmful when there is nothing to reorder."""
    events = [
        _event(CanonicalEventType.CREATE_USER_REQUESTED, full_name="Hysamm"),
        _event(CanonicalEventType.PROJECT_CREATE_REQUESTED, name="Paraclette"),
    ]
    result = build_plan_from_segments(events, plan_id="plan_1")
    assert [s.step_id for s in result.plan.steps] == ["s1", "s2"]
