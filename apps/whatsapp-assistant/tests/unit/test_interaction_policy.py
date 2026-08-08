"""InteractionDecision policy — unit tests."""

from __future__ import annotations

import pytest

from interactions.intent import InteractionIntent
from interactions.policy import InteractionDecision, InteractionRoute, decide
from workflows import ResumeAction


@pytest.mark.parametrize(
    "intent,route,action",
    [
        (InteractionIntent.CONFIRM, InteractionRoute.RESUME, ResumeAction.CONFIRM),
        (InteractionIntent.REJECT, InteractionRoute.RESUME, ResumeAction.REJECT),
        (InteractionIntent.CANCEL, InteractionRoute.RESUME, ResumeAction.CANCEL),
        (InteractionIntent.CORRECTION, InteractionRoute.NEW_JOURNEY, None),
        (InteractionIntent.UNRELATED, InteractionRoute.NEW_JOURNEY, None),
        (InteractionIntent.AMBIGUOUS, InteractionRoute.NEW_JOURNEY, None),
    ],
)
def test_decide(intent, route, action):
    d = decide(intent)
    assert d.route is route
    assert d.resume_action is action


def test_resume_requires_action():
    with pytest.raises(ValueError):
        InteractionDecision(route=InteractionRoute.RESUME, resume_action=None)


def test_new_journey_forbids_action():
    with pytest.raises(ValueError):
        InteractionDecision(route=InteractionRoute.NEW_JOURNEY, resume_action=ResumeAction.CONFIRM)
