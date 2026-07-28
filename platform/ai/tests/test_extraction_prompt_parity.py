"""The extraction prompts must not drift apart between providers.

Which model answers a message is a deployment detail -- the same WhatsApp
message has to produce the same structured result either way. The prompts
are maintained as separate strings per adapter, so they drift silently, and
that drift has now caused three production bugs:

1. DeepSeek's semantic-type list was missing labour_query and
   activity_query, so "how many workers today?" could not be recognised at
   all while that provider was active.
2. DeepSeek's labour schema still asked for a flat `headcount`/`trade` long
   after Gemini's asked for a `workers` array -- so a report naming people
   came back with no names, and every named worker silently vanished into a
   headcount.
3. Only Gemini was told to transliterate a non-Latin name, so a Malayalam
   voice note left Malayalam script sitting in worker_name, where it cannot
   match the register and cannot be typed back by a supervisor.

Each was found in production, by a person, after the fact. These tests are
deliberately coarse -- they assert the *contract* both prompts must state,
not their wording, so the prompts stay free to differ in phrasing while the
things a caller depends on stay identical.
"""

from __future__ import annotations

import pytest

from mesiri_ai.adapters.deepseek.adapter import _EXTRACTION_PROMPT as DEEPSEEK_PROMPT
from mesiri_ai.adapters.gemini.adapter import _EXTRACTION_PROMPT as GEMINI_PROMPT
from mesiri_contracts.assistant.enums import SemanticType

PROMPTS = {"deepseek": DEEPSEEK_PROMPT, "gemini": GEMINI_PROMPT}


@pytest.mark.parametrize("provider", sorted(PROMPTS))
@pytest.mark.parametrize("semantic", [s.value for s in SemanticType])
def test_every_semantic_type_is_offered_to_every_provider(provider, semantic):
    """A type the model is never told about is a type it can never return.

    UNKNOWN is included deliberately: it is the honest answer for an
    unrecognised message, and a model that has not been offered it will
    guess something else instead.
    """
    assert semantic in PROMPTS[provider], (
        f"{provider} is never told about semantic_type {semantic!r}"
    )


@pytest.mark.parametrize("provider", sorted(PROMPTS))
def test_labour_is_asked_for_a_workers_array_not_a_flat_headcount(provider):
    """The whole named-worker feature depends on this shape. A prompt asking
    only for headcount/trade cannot express "Ravi, mason" at all."""
    prompt = PROMPTS[provider]
    assert "workers (array)" in prompt, f"{provider} does not ask for a workers array"
    assert '"headcount" (how many people this line covers' in prompt, (
        f"{provider} does not define headcount per line"
    )


@pytest.mark.parametrize("provider", sorted(PROMPTS))
def test_names_must_be_transliterated_and_the_original_kept(provider):
    """Malayalam left in worker_name matches nothing in the register and
    cannot be typed back by a supervisor correcting it."""
    prompt = PROMPTS[provider]
    assert "transliterate" in prompt.lower(), f"{provider} never asks for transliteration"
    assert "name_original" in prompt, f"{provider} never asks for the original spelling"


@pytest.mark.parametrize("provider", sorted(PROMPTS))
def test_a_name_is_never_translated_into_a_word(provider):
    """"Ravi" is a person, not vocabulary. A model translating names turns a
    worker into an English noun and loses them entirely."""
    assert "never translate a name" in PROMPTS[provider].lower(), (
        f"{provider} does not forbid translating a name"
    )


@pytest.mark.parametrize("provider", sorted(PROMPTS))
def test_a_name_is_never_invented_for_an_unnamed_group(provider):
    """"12 helpers" names nobody. An invented name would be recorded as a
    real person and offered for the permanent register."""
    assert "never invent a name" in PROMPTS[provider].lower(), (
        f"{provider} does not forbid inventing a name"
    )
