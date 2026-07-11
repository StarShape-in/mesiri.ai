"""channel/replies.py — the planner-leg reply renderers.

Before these existed, CLARIFY and DIRECT_REPLY were computed by the Planner,
logged, and dropped; every such message fell through to format_reply()'s
developer diagnostic. These tests pin the replies a user actually receives.
"""

from __future__ import annotations

from channel.replies import (
    CATEGORY_ROWS,
    render_category_prompt,
    render_clarify_reply,
    render_direct_reply,
    render_no_projects_reply,
    render_project_picker,
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
        _decision(
            PlannerDecisionType.CLARIFY, CanonicalEventType.CLARIFICATION_REQUIRED, ["quantity"]
        )
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


def test_first_message_offers_examples_of_what_mesiri_can_record():
    """Only the first-ever greeting spells out examples in the text body --
    a returning user gets the short "what are you reporting" prompt and
    relies on the tappable menu instead (see test_first_message_gets_...)."""
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
        is_first_message=True,
    )
    assert "cement" in reply.text


def test_greeting_carries_the_four_category_rows_and_nothing_else():
    """Only the greeting/unrecognized reply ever carries a menu -- and it's
    exactly the four locked v1 modules, not Equipment and Machinery split
    into two, and not a fifth 'Site Update' or similar sneaking in."""
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED)
    )
    assert reply.list_rows == CATEGORY_ROWS
    assert [row.title for row in reply.list_rows] == [
        "Material",
        "Equipment & Machinery",
        "Labour",
        "Expense",
    ]
    assert reply.list_button_label


def test_greeting_is_time_aware_in_the_users_timezone():
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
        timezone="Asia/Kolkata",
    )
    assert any(g in reply.text for g in ("Good morning", "Good afternoon", "Good evening"))


def test_greeting_falls_back_to_hello_on_unknown_timezone():
    """A wrong 'Good morning' at 9pm is worse than no time of day at all."""
    for tz in (None, "Not/AZone"):
        reply = render_direct_reply(
            _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
            timezone=tz,
        )
        assert reply.text.startswith("Hello")


def test_first_message_gets_introduced_returning_user_does_not():
    """A returning user who already knows what Mesiri does shouldn't be
    re-introduced on every 'hi' -- only the first-ever message explains what
    the assistant is."""
    first = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
        is_first_message=True,
    )
    returning = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.UNRECOGNIZED),
        is_first_message=False,
    )
    assert "I'm Mesiri" in first.text
    assert "I'm Mesiri" not in returning.text
    # Both still offer the same tappable menu -- only the copy differs.
    assert first.list_rows == returning.list_rows == CATEGORY_ROWS


def test_question_gets_capability_answer_not_a_greeting():
    reply = render_direct_reply(
        _decision(PlannerDecisionType.DIRECT_REPLY, CanonicalEventType.GENERAL_QUESTION_ASKED)
    )
    assert "record" in reply.text
    assert not reply.text.startswith(("Hello", "Good "))
    # A question that's already understood as a question doesn't need a menu.
    assert reply.list_rows is None


def test_category_prompt_is_deterministic_per_row_and_distinct():
    prompts = {render_category_prompt(row.id) for row in CATEGORY_ROWS}
    assert None not in prompts
    assert len(prompts) == len(CATEGORY_ROWS)  # no two categories share a prompt


def test_category_prompt_is_none_for_an_unknown_row_id():
    """A stale button from an old message, or a tampered payload, must not
    produce a reply at all -- the caller falls through to the normal journey."""
    assert render_category_prompt("cat_does_not_exist") is None


def test_unsupported_is_distinct_from_not_understood():
    """Telling someone who reported an expense that we 'couldn't make out' their
    message sends them rephrasing a message that was never the problem."""
    assert render_unsupported_reply() != render_understanding_failed_reply()
    assert "couldn't make out" not in render_unsupported_reply()


def test_project_picker_lists_every_project_with_prefixed_row_ids():
    reply = render_project_picker([("prj_1", "Site A", "Kochi"), ("prj_2", "Site B", None)])
    assert reply.list_rows is not None
    assert [row.id for row in reply.list_rows] == ["proj_prj_1", "proj_prj_2"]
    assert [row.title for row in reply.list_rows] == ["Site A", "Site B"]


def test_project_picker_caps_at_ten_rows():
    projects = [(f"prj_{i}", f"Project {i}", None) for i in range(15)]
    reply = render_project_picker(projects)
    assert reply.list_rows is not None
    assert len(reply.list_rows) == 10


def test_no_projects_reply_is_distinct_from_the_picker():
    assert render_no_projects_reply() != render_project_picker([]).text
