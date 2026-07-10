"""InteractionIntent — what the user meant by a reply (classifier output).

Distinct from InteractionDecision (what the system will do). Deterministic
classification of a reply while a workflow awaits confirmation.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.interaction_spec import InteractionIntent

__all__ = ["InteractionIntent"]
