"""Text translation port (M3).

Turns raw text in any language into English text using an LLM or translation API.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import TranslationResult


@runtime_checkable
class TranslationProvider(Protocol):
    async def translate_to_english(
        self,
        text: str,
        *,
        correlation_id: str | None = None,
    ) -> TranslationResult:
        """Translate arbitrary text to English."""
        ...
