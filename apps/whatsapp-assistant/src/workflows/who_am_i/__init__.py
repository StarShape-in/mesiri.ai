"""who_am_i -- deterministic identity-lookup trigger ("who am i", "whoami", ...).

Not a LangGraph workflow like material/expense_capture (no multi-turn state,
no confirmation, nothing to checkpoint) -- a single-turn fast path, kept in
its own folder under workflows/ purely for discoverability alongside the
other workflow-shaped features, not because it shares their runtime.

The actual classifier lives in mesiri_ai.whoami_classifier, not here --
understanding/pipeline.py needs it too, and understanding/ must not import
from workflows/ (dependency direction). This re-export exists so
interactions/handler.py's existing `from workflows.who_am_i import
is_whoami_trigger` keeps working unchanged.
"""

from __future__ import annotations

from mesiri_ai.whoami_classifier import is_whoami_trigger

__all__ = ["is_whoami_trigger"]
