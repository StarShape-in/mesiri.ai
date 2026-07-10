"""JSON generation port (M3).

Allows prompting an LLM for structured JSON output without tying callers to a specific provider SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class JsonGenerationProvider(Protocol):
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        correlation_id: str | None = None,
    ) -> str:
        """Generate a JSON string from the given prompts."""
        ...
