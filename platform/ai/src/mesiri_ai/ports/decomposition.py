"""Decomposition provider port (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md
§9).

Splits (never classifies) a message that extraction already returned
"unknown" for, into its constituent sub-texts. Callers depend on this
protocol, never on a provider SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import DecompositionResult


@runtime_checkable
class DecompositionProvider(Protocol):
    provider: str

    async def decompose(
        self,
        text: str,
        *,
        correlation_id: str | None = None,
    ) -> DecompositionResult:
        """``text`` is already known to have failed single-intent
        extraction (semantic_type == unknown) -- the caller's job, not this
        one. This call decides only whether that failure was because the
        message states several distinct requests at once, and if so, where
        they split."""
        ...
