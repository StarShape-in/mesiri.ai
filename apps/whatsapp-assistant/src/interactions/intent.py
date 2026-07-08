"""InteractionIntent — what the user meant by a reply (classifier output).

Distinct from InteractionDecision (what the system will do). Deterministic
classification of a reply while a workflow awaits confirmation.
"""

from __future__ import annotations

from enum import Enum


class InteractionIntent(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    CANCEL = "cancel"
    CORRECTION = "correction"  # deferred in M7 — routed to a new journey
    UNRELATED = "unrelated"    # a new intent, not a reply to the pending workflow
    AMBIGUOUS = "ambiguous"    # conflicting signals (e.g. "yes no")
