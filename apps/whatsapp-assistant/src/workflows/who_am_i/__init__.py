"""who_am_i -- deterministic identity-lookup trigger ("who am i", "whoami", ...).

Not a LangGraph workflow like material/expense_capture (no multi-turn state,
no confirmation, nothing to checkpoint) -- a single-turn fast path, kept in
its own folder under workflows/ purely for discoverability alongside the
other workflow-shaped features, not because it shares their runtime.
"""

from __future__ import annotations

from .classifier import is_whoami_trigger

__all__ = ["is_whoami_trigger"]
