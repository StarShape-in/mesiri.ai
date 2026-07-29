"""SlotAnswerClassifierPort — LLM classification for a picker reply the
deterministic matcher (workflows/slots.py's match_slot_answer) couldn't
resolve."""

from __future__ import annotations

from typing import Protocol

from workflows.slots import SlotCandidate


class SlotAnswerClassifierPort(Protocol):
    """Port for resolving a free-text reply against a slot's candidate list."""

    async def classify(
        self,
        reply_text: str,
        candidates: tuple[SlotCandidate, ...],
        correlation_id: str,
    ) -> str | None:
        """Return the matched candidate's `value`, or None if the reply
        doesn't clearly pick one."""
        ...
