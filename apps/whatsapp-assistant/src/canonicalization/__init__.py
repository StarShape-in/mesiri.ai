"""Canonicalization — normalizes UnderstandingResult + ResolvedContext into CanonicalEvent.

Single responsibility: bridge Context (M4) and Planner (M5). Depends only on
`mesiri_contracts.assistant.*` — no ports, no I/O, no AI SDKs, no persistence.
"""

from __future__ import annotations

from .builder import build_canonical_event, build_canonical_events, log_canonical_event

__all__ = ["build_canonical_event", "build_canonical_events", "log_canonical_event"]
