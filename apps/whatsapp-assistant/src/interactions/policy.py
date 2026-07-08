"""InteractionDecision — what the system will do with a classified reply.

The explicit decision the architecture review demanded: a message is resumed
into the pending workflow *only* when the policy says so. CONFIRM/REJECT/CANCEL
resume; everything else (CORRECTION deferred, UNRELATED, AMBIGUOUS) falls
through to a fresh understanding journey.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from workflows import ResumeAction

from .intent import InteractionIntent


class InteractionRoute(str, Enum):
    RESUME = "resume"
    NEW_JOURNEY = "new_journey"


@dataclass(frozen=True, slots=True)
class InteractionDecision:
    route: InteractionRoute
    resume_action: ResumeAction | None = None

    def __post_init__(self) -> None:
        if self.route is InteractionRoute.RESUME and self.resume_action is None:
            raise ValueError("RESUME requires a resume_action")
        if self.route is InteractionRoute.NEW_JOURNEY and self.resume_action is not None:
            raise ValueError("NEW_JOURNEY must not carry a resume_action")


_RESUME_ACTION: dict[InteractionIntent, ResumeAction] = {
    InteractionIntent.CONFIRM: ResumeAction.CONFIRM,
    InteractionIntent.REJECT: ResumeAction.REJECT,
    InteractionIntent.CANCEL: ResumeAction.CANCEL,
}


def decide(intent: InteractionIntent) -> InteractionDecision:
    action = _RESUME_ACTION.get(intent)
    if action is None:
        # CORRECTION (deferred), UNRELATED, AMBIGUOUS → let the normal pipeline run.
        return InteractionDecision(route=InteractionRoute.NEW_JOURNEY)
    return InteractionDecision(route=InteractionRoute.RESUME, resume_action=action)
