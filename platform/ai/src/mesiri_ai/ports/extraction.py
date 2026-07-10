"""Structured-extraction provider port (M3).

Turns normalized text (from a text message, a transcript, or a vision
description) into a structured :class:`ExtractionResult`. Callers depend on this
protocol, never on a provider SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import ExtractionResult


@runtime_checkable
class StructuredExtractionProvider(Protocol):
    async def extract(
        self,
        text: str,
        *,
        semantic_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> ExtractionResult: ...
