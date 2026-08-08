"""InteractionClassifierPort — lightweight LLM classifier for the slow path."""

from __future__ import annotations

from typing import Any, Protocol

from mesiri_contracts.assistant.v2.interaction_spec import InteractionSpecV2


class InteractionClassifierPort(Protocol):
    """Port for classifying an interaction reply (e.g. voice note transcript)."""

    async def classify(
        self,
        original_text: str,
        translated_text: str | None,
        draft_fields: dict[str, Any],
        correlation_id: str,
    ) -> InteractionSpecV2:
        """Classify the text against the pending draft fields."""
        ...
