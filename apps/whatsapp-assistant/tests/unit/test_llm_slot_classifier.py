"""AdapterSlotAnswerClassifier -- unit tests (fake JSON provider, no real LLM)."""

from __future__ import annotations

from interactions.llm_slot_classifier import AdapterSlotAnswerClassifier
from workflows.slots import SlotCandidate

CANDIDATES = (
    SlotCandidate(value="act-1", label="plastering — started plastering on 2nd floor"),
    SlotCandidate(value="new_activity", label="This is new work"),
)


class _FakeJsonProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str, str | None]] = []

    async def generate_json(self, system_prompt: str, user_prompt: str, *, correlation_id=None) -> str:
        self.calls.append((system_prompt, user_prompt, correlation_id))
        return self.response


async def test_resolves_to_the_matched_candidates_value():
    provider = _FakeJsonProvider('{"matched_index": 2}')
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("New cause it's 3rd floor", CANDIDATES, "cor_1")
    assert result == "new_activity"


async def test_passes_reply_text_and_correlation_id_through():
    provider = _FakeJsonProvider('{"matched_index": 1}')
    classifier = AdapterSlotAnswerClassifier(provider)
    await classifier.classify("the plastering one", CANDIDATES, "cor_42")
    _, user_prompt, correlation_id = provider.calls[0]
    assert user_prompt == "the plastering one"
    assert correlation_id == "cor_42"


async def test_null_match_returns_none():
    provider = _FakeJsonProvider('{"matched_index": null}')
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("something totally unrelated", CANDIDATES, "cor_1")
    assert result is None


async def test_out_of_range_index_returns_none():
    provider = _FakeJsonProvider('{"matched_index": 99}')
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("huh", CANDIDATES, "cor_1")
    assert result is None


async def test_malformed_json_returns_none_not_raise():
    provider = _FakeJsonProvider("not json at all")
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("2", CANDIDATES, "cor_1")
    assert result is None


async def test_code_fenced_json_is_parsed():
    provider = _FakeJsonProvider('```json\n{"matched_index": 2}\n```')
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("new one", CANDIDATES, "cor_1")
    assert result == "new_activity"


async def test_provider_exception_returns_none_not_raise():
    class _ExplodingProvider:
        async def generate_json(self, system_prompt, user_prompt, *, correlation_id=None):
            raise RuntimeError("boom")

    classifier = AdapterSlotAnswerClassifier(_ExplodingProvider())
    result = await classifier.classify("2", CANDIDATES, "cor_1")
    assert result is None


async def test_no_candidates_returns_none_without_calling_provider():
    provider = _FakeJsonProvider('{"matched_index": 1}')
    classifier = AdapterSlotAnswerClassifier(provider)
    result = await classifier.classify("anything", (), "cor_1")
    assert result is None
    assert provider.calls == []
