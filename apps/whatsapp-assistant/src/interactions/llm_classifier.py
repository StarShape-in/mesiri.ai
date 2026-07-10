"""LLM-backed slow-path classifier for complex interactions."""

import json
import logging
from typing import Any

from mesiri_contracts.assistant.v2.interaction_spec import (
    FieldCorrection,
    InteractionIntent,
    InteractionSegment,
    InteractionSpecV2,
)

logger = logging.getLogger(__name__)

_SEGMENTER_PROMPT = """You are analyzing a user's reply to a pending workflow draft. The user may provide multiple distinct thoughts in one message.

INSTRUCTIONS:
1. Read the original transcript and the English translation.
2. Separate the message into distinct topical intents (e.g., CONFIRM, CORRECTION, UNRELATED).
3. For each topic, generate a `segment_text` in English. 
   - CRITICAL: The `segment_text` must be entirely self-contained. You must resolve any pronouns ("it", "they") or dropped subjects (common in Malayalam) using the context of the pending draft. 
   - If the user says "ask them to deliver tomorrow" and the draft is about 50 bags of cement from ABC Hardware, the `segment_text` should be "ask ABC Hardware to deliver the 50 bags of cement tomorrow".
4. Classify the `intent` for each segment independently (CONFIRM, REJECT, CANCEL, CORRECTION, UNRELATED, AMBIGUOUS).

Output JSON array of objects:
[
  {
    "intent": "CORRECTION",
    "segment_text": "..."
  }
]
"""

_EXTRACTOR_PROMPT = """You are a JSON extractor. You are given a single focused request (a segment) that represents a CORRECTION to a pending draft.
You must return the specific field corrections. 

Draft Fields: {draft_fields}

Identify which fields need to change and return them as a JSON array of objects:
[
  {
    "field_name": "exact_field_name_from_draft",
    "new_value": value
  }
]
"""

from mesiri_ai.ports.generation import JsonGenerationProvider


class AdapterInteractionClassifier:
    """Uses a two-call pipeline to segment intents and extract corrections via an AI adapter."""

    def __init__(self, json_generation: JsonGenerationProvider) -> None:
        self._json = json_generation

    async def classify(
        self,
        original_text: str,
        translated_text: str | None,
        draft_fields: dict[str, Any],
        correlation_id: str,
    ) -> InteractionSpecV2:
        # Call 1: Segmenter
        sys_prompt = _SEGMENTER_PROMPT
        user_msg = f"Draft Fields: {json.dumps(draft_fields)}\n\nOriginal: {original_text}\nTranslated: {translated_text or 'N/A'}"

        segmenter_reply = await self._json.generate_json(
            system_prompt=sys_prompt, user_prompt=user_msg, correlation_id=correlation_id
        )

        try:
            segments_data = json.loads(segmenter_reply)
        except json.JSONDecodeError as err:
            logger.error("Failed to parse segmenter output: %s", segmenter_reply)
            raise ValueError("Failed to parse segmenter output") from err

        segments = []
        for s in segments_data:
            intent = InteractionIntent(s["intent"].lower())
            segment_text = s["segment_text"]
            corrections = []

            if intent == InteractionIntent.CORRECTION:
                # Call 2: Extractor
                ext_sys = _EXTRACTOR_PROMPT.replace("{draft_fields}", json.dumps(draft_fields))
                ext_user = f"Segment to correct: {segment_text}"

                extractor_reply = await self._json.generate_json(
                    system_prompt=ext_sys, user_prompt=ext_user, correlation_id=correlation_id
                )
                try:
                    corr_data = json.loads(extractor_reply)
                    for c in corr_data:
                        corrections.append(
                            FieldCorrection(field_name=c["field_name"], new_value=c["new_value"])
                        )
                except json.JSONDecodeError as err:
                    logger.error("Failed to parse extractor output: %s", extractor_reply)
                    raise ValueError("Failed to parse extractor output") from err
                except Exception as e:
                    logger.error("Failed to map corrections: %s", e)
                    raise

            segments.append(
                InteractionSegment(
                    intent=intent, segment_text=segment_text, corrections=corrections
                )
            )

        return InteractionSpecV2(correlation_id=correlation_id, segments=segments)
