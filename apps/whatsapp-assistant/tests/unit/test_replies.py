"""channel/replies.py — the planner-leg reply renderers.

Before these existed, CLARIFY and DIRECT_REPLY were computed by the Planner,
logged, and dropped; every such message fell through to format_reply()'s
developer diagnostic. These tests pin the replies a user actually receives.
"""

from __future__ import annotations

from channel.replies import (
    render_clarify_reply,
    render_direct_reply,
    render_understanding_failed_reply,
    render_unsupported_reply,
)
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2

_ORG = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"


def _decision(
    decision_type: PlannerDecisionType,
    reason: CanonicalEventType,
    missing: list[str] | None = None,
) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=decision_type,
        reason=reason,
        organization_id=_ORG,
        user_id=_USER,
        missing_fields=missing or [],
    )


def test_clarify_names_a_single_missing_field_in_plain_words():
    reply = render_clarify_reply(
        _decision(PlannerDecisionType.CLARIFY, CanonicalEventType.CLARIFICATION_REQUIRED, ["quantity"])
    )
    assert "how much" in reply
    assert "quantity" not in reply  # schema names must not leak to the user


def test_clarify_joins_several_missing_fields_readably():
    reply = render_clarify_reply(
        _decision(
            PlannerDecisionType.CLARIFY,
            CanonicalEventType.CLARIFICATION_REQUIRED,
            ["quantity", "unit"],
        )
    )
    assert "how much" in reply and "and" in reply


def test_clarify_with_no_missing_fields_still_asks_something():
    """Defensive: a CLARIFY should always carry missing_fields, but an empty
    question is worse than a generic one."""
    reply = render_clarify_reply(
        _decision(PlannerDecisionType.CLARIFY, CanonicalEventType.CLARIFICATION_REQUIRED, [])
    )
    assert reply.strip()


def test_greeting_offers_examples_of_what_mesiri_can_record():
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED)
    )
    assert "cement" in reply


def test_greeting_is_time_aware_in_the_users_timezone():
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
        timezone="Asia/Kolkata",
    )
    assert any(g in reply for g in ("Good morning", "Good afternoon", "Good evening"))


def test_greeting_falls_back_to_hello_on_unknown_timezone():
    """A wrong 'Good morning' at 9pm is worse than no time of day at all."""
    for tz in (None, "Not/AZone"):
        reply = render_direct_reply(
            _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
            timezone=tz,
        )
        assert reply.startswith("Hello")


def test_question_gets_capability_answer_not_a_greeting():
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.GENERAL_QUESTION_ASKED)
    )
    assert "record" in reply
    assert not reply.startswith(("Hello", "Good "))


def test_unsupported_is_distinct_from_not_understood():
    """Telling someone who reported an expense that we 'couldn't make out' their
    message sends them rephrasing a message that was never the problem."""
    assert render_unsupported_reply() != render_understanding_failed_reply()
    assert "couldn't make out" not in render_unsupported_reply()
