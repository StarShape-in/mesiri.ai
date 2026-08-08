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
    provider: str

    async def extract(
        self,
        text: str,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> ExtractionResult:
        """``expense_categories``, when given, is the caller org's active
        expense_categories names — the provider should pick one of these
        verbatim for an expense's `category` field when the text supports
        it, rather than inventing a new label (see resolution.py's
        exact-match resolver, which this keeps in sync with)."""
        ...
