"""LLM-backed classifier for a picker reply the deterministic matcher missed.

workflows/slots.py's match_slot_answer only matches a bare number or a whole-
string substring against a candidate label -- a reply like "New cause it's
3rd floor" isn't a substring of "This is new work" (or vice versa), so it
fails even though the intent is unambiguous to a human. This adapter is
consulted by interactions/handler.py's handle_slot_answer only after that
deterministic pass has already failed once (re-asked with the same
candidates), so a plain number or exact label reply never reaches here --
same "a plain reply costs no tokens" principle as llm_classifier.py.
"""

from __future__ import annotations

import json
import logging
import time

from mesiri_ai.ports.generation import JsonGenerationProvider
from runtime.logging_ports import TraceLogger
from runtime.noop_loggers import NoopTraceLogger
from workflows.slots import SlotCandidate

logger = logging.getLogger(__name__)

_SLOT_CLASSIFY_PROMPT = """You are matching a user's free-text reply to one option from a numbered list they were just shown.

Options:
{options_block}

The user replied: "{reply_text}"

Decide which option (by number) the user means, even if their reply wraps the
choice in extra words, justification, or context. If the reply genuinely
doesn't match any option, or is unrelated/ambiguous, say so.

Output JSON only: {{"matched_index": <1-based number, or null>}}
"""


class AdapterSlotAnswerClassifier:
    """Single-call classification via an AI adapter's generate_json."""

    def __init__(
        self,
        json_generation: JsonGenerationProvider,
        *,
        trace_logger: TraceLogger | None = None,
    ) -> None:
        self._json = json_generation
        self._trace_logger: TraceLogger = trace_logger or NoopTraceLogger()

    async def classify(
        self,
        reply_text: str,
        candidates: tuple[SlotCandidate, ...],
        correlation_id: str,
    ) -> str | None:
        if not candidates:
            return None
        options_block = "\n".join(f"{i}. {c.label}" for i, c in enumerate(candidates, start=1))
        sys_prompt = _SLOT_CLASSIFY_PROMPT.format(options_block=options_block, reply_text=reply_text)

        t0 = time.perf_counter()
        try:
            raw = await self._json.generate_json(
                system_prompt=sys_prompt, user_prompt=reply_text, correlation_id=correlation_id
            )
        except Exception as exc:  # noqa: BLE001 -- never block the reply on a broken LLM call
            await self._trace_logger.log_stage(
                correlation_id=correlation_id,
                stage="slot_answer_classify",
                stage_payload={"candidate_count": len(candidates)},
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            logger.warning("slot_answer_classify.failed correlation_id=%s error=%s", correlation_id, exc)
            return None

        await self._trace_logger.log_stage(
            correlation_id=correlation_id,
            stage="slot_answer_classify",
            stage_payload={"candidate_count": len(candidates)},
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=True,
        )

        try:
            data = json.loads(_strip_code_fence(raw))
            index = data.get("matched_index")
        except (json.JSONDecodeError, AttributeError, TypeError):
            logger.warning("slot_answer_classify.malformed_output correlation_id=%s raw=%r", correlation_id, raw)
            return None

        if not isinstance(index, int):
            return None
        position = index - 1
        if not (0 <= position < len(candidates)):
            return None
        return candidates[position].value


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()
