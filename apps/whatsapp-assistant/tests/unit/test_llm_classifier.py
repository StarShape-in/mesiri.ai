"""AdapterInteractionClassifier -- unit tests (fake JSON provider, no real LLM).

No test file existed for this adapter before -- covers the segmenter/
extractor JSON-parsing plumbing. Cannot verify real model judgment on
_SEGMENTER_PROMPT's "wrong record type vs. wrong field value" rule (that's a
prompt-quality question, not something a fake-provider unit test can prove);
see the plan's Verification section for why that's watched via production
traces instead.
"""

from __future__ import annotations

import json

import pytest

from interactions.llm_classifier import _SEGMENTER_PROMPT, AdapterInteractionClassifier
from mesiri_contracts.assistant.v2.interaction_spec import FieldCorrection, InteractionIntent


class _FakeJsonProvider:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, str | None]] = []

    async def generate_json(self, system_prompt: str, user_prompt: str, *, correlation_id=None) -> str:
        self.calls.append((system_prompt, user_prompt, correlation_id))
        return self._responses.pop(0)


async def test_confirm_segment_needs_no_extractor_call():
    provider = _FakeJsonProvider([json.dumps([{"intent": "CONFIRM", "segment_text": "yes"}])])
    classifier = AdapterInteractionClassifier(provider)

    spec = await classifier.classify("yes", "yes", {"quantity": 4}, "cor_1")

    assert len(spec.segments) == 1
    assert spec.segments[0].intent == InteractionIntent.CONFIRM
    assert spec.segments[0].corrections == []
    assert len(provider.calls) == 1  # segmenter only, no extractor call


async def test_correction_segment_triggers_extractor_call():
    provider = _FakeJsonProvider(
        [
            json.dumps([{"intent": "CORRECTION", "segment_text": "make it 5 bags"}]),
            json.dumps([{"field_name": "quantity", "new_value": 5}]),
        ]
    )
    classifier = AdapterInteractionClassifier(provider)

    spec = await classifier.classify("make it 5 not 4", "make it 5 not 4", {"quantity": 4}, "cor_1")

    assert spec.segments[0].intent == InteractionIntent.CORRECTION
    assert spec.segments[0].corrections == [FieldCorrection(field_name="quantity", new_value=5)]
    assert len(provider.calls) == 2


async def test_reject_and_unrelated_segments_need_no_extractor_call():
    """The case this prompt change targets: "this isn't an issue, it's an
    activity" should segment into REJECT + UNRELATED, neither of which
    carries corrections or needs the extractor."""
    provider = _FakeJsonProvider(
        [
            json.dumps(
                [
                    {"intent": "REJECT", "segment_text": "this is not a site issue"},
                    {
                        "intent": "UNRELATED",
                        "segment_text": "slab work on the 4th floor has started",
                    },
                ]
            )
        ]
    )
    classifier = AdapterInteractionClassifier(provider)

    spec = await classifier.classify(
        "issue alla, slab work thudangi", "it's not an issue, slab work started", {"issue_type": "OTHER"}, "cor_1"
    )

    assert [s.intent for s in spec.segments] == [InteractionIntent.REJECT, InteractionIntent.UNRELATED]
    assert all(s.corrections == [] for s in spec.segments)
    assert len(provider.calls) == 1


async def test_malformed_segmenter_json_raises():
    provider = _FakeJsonProvider(["not json"])
    classifier = AdapterInteractionClassifier(provider)

    with pytest.raises(ValueError, match="segmenter"):
        await classifier.classify("huh", "huh", {}, "cor_1")


async def test_malformed_extractor_json_raises():
    provider = _FakeJsonProvider(
        [json.dumps([{"intent": "CORRECTION", "segment_text": "make it 5 bags"}]), "not json"]
    )
    classifier = AdapterInteractionClassifier(provider)

    with pytest.raises(ValueError, match="extractor"):
        await classifier.classify("make it 5", "make it 5", {"quantity": 4}, "cor_1")


def test_segmenter_prompt_documents_the_wrong_record_type_rule():
    """Golden-string guard: the fix for "issue alla, activity aanu" being
    misread as CORRECTION is this instruction existing at all -- a prompt
    edit that silently regresses (e.g. an unrelated rewrite drops it) would
    otherwise have no test to catch it."""
    assert "wrong record type" in _SEGMENTER_PROMPT.lower()
    assert "REJECT" in _SEGMENTER_PROMPT
