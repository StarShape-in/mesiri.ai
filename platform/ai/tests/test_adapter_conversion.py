"""Adapter response conversion (M3) — no network, no SDK required.

Verifies that adapters convert provider-shaped responses into Mesiri-owned
models and that malformed provider output maps to the shared error contract.
The SDK calls themselves are exercised only in provider-marked tests.
"""

from types import SimpleNamespace

import pytest

from mesiri_ai.adapters.gemini.adapter import GeminiProvider
from mesiri_ai.adapters.sarvam.adapter import SarvamSpeechProvider
from mesiri_contracts.common.errors import MesiriError


def test_sarvam_converts_dict_response_to_speech_result():
    provider = SarvamSpeechProvider.__new__(SarvamSpeechProvider)  # skip SDK init
    raw = {"transcript": "The JCB ran for 4 hours", "language_code": "ml-IN"}
    result = provider._to_result(raw, latency_ms=120.0)
    assert result.transcript == "The JCB ran for 4 hours"
    assert result.detected_language == "ml-IN"
    assert result.translated_text == "The JCB ran for 4 hours"
    assert result.latency_ms == 120.0


def test_gemini_parses_fenced_json():
    data = GeminiProvider._parse_json('```json\n{"semantic_type": "expense"}\n```', None)
    assert data["semantic_type"] == "expense"


def test_gemini_malformed_output_maps_to_error():
    with pytest.raises(MesiriError) as exc:
        GeminiProvider._parse_json("not json at all", correlation_id="cor_x")
    assert exc.value.error_code == "PROVIDER_MALFORMED_OUTPUT"
    assert exc.value.correlation_id == "cor_x"


def test_gemini_non_object_json_is_malformed():
    with pytest.raises(MesiriError):
        GeminiProvider._parse_json("[1, 2, 3]", None)


def test_gemini_parses_json_wrapped_in_leading_commentary():
    """Regression test: a live bug where an inventory query naming a project
    inline in Malayalam ("Green Valley-ൽ...") failed translation every time,
    at any sentence length. Root cause: Gemini sometimes adds a clarifying
    sentence around the JSON for code-mixed input (an English proper noun
    embedded in a non-English sentence) -- e.g. explaining that "Green
    Valley" was left untranslated -- which the old exact-fence-stripping
    parser couldn't handle at all, throwing a non-retryable error that
    propagated all the way to "couldn't make out that message". json_mode
    (response_mime_type) should prevent this at the source now, but the
    parser must still degrade gracefully if a model ever does it anyway."""
    raw = (
        'Note: "Green Valley" appears to be a proper name and was left untranslated.\n'
        '{"translated_text": "In Green Valley, how many bags of cement are in stock?", '
        '"detected_language": "Malayalam"}'
    )
    data = GeminiProvider._parse_json(raw, None)
    assert data["translated_text"] == "In Green Valley, how many bags of cement are in stock?"


def test_gemini_parses_json_wrapped_in_trailing_commentary():
    raw = (
        '{"semantic_type": "inventory_query", "fields": {"project_name": "Green Valley"}}\n'
        "(Note: material_name omitted since the user asked about all materials.)"
    )
    data = GeminiProvider._parse_json(raw, None)
    assert data["semantic_type"] == "inventory_query"
    assert data["fields"]["project_name"] == "Green Valley"


def test_gemini_still_rejects_response_with_no_json_object_at_all():
    """The commentary-tolerant fallback must not silently accept text that
    never contained a JSON object in the first place -- that's still a real
    provider failure, not something to paper over."""
    with pytest.raises(MesiriError) as exc:
        GeminiProvider._parse_json("I'm sorry, I don't understand this request.", None)
    assert exc.value.error_code == "PROVIDER_MALFORMED_OUTPUT"


async def test_gemini_json_mode_sets_response_mime_type():
    """extract()/translate_to_english()/analyze_image()/generate_json() must
    ask Gemini for a strict-JSON response (response_mime_type=
    "application/json") -- the primary defense against the commentary-
    wrapped-JSON bug above, stopping it at the source rather than relying
    only on _parse_json's fallback parsing."""
    captured: dict = {}

    class _FakeModels:
        def generate_content(self, *, model, contents, config=None):
            captured["config"] = config
            return SimpleNamespace(text='{"translated_text": "hello", "detected_language": "en"}')

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = SimpleNamespace(
        model="gemini-test", timeout_seconds=5, max_retries=0
    )
    provider._client = SimpleNamespace(models=_FakeModels())

    await provider.translate_to_english("hello", correlation_id="cor_1")

    assert captured["config"] is not None
    assert captured["config"].response_mime_type == "application/json"


async def test_gemini_transcribe_does_not_force_json_mode():
    """transcribe() returns a plain transcript, not JSON -- it must NOT set
    response_mime_type (that would make Gemini try to wrap plain speech
    text in a JSON envelope it was never asked to produce)."""
    captured: dict = {}

    class _FakeModels:
        def generate_content(self, *, model, contents, config=None):
            captured["config"] = config
            return SimpleNamespace(text="the transcript")

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = SimpleNamespace(
        model="gemini-test", timeout_seconds=5, max_retries=0
    )
    provider._client = SimpleNamespace(models=_FakeModels())

    await provider.transcribe(b"audio-bytes", correlation_id="cor_1")

    assert captured["config"] is None
