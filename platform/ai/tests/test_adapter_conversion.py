"""Adapter response conversion (M3) — no network, no SDK required.

Verifies that adapters convert provider-shaped responses into Mesiri-owned
models and that malformed provider output maps to the shared error contract.
The SDK calls themselves are exercised only in provider-marked tests.
"""

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
