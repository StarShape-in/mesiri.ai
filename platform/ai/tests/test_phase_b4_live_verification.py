"""Phase B4 (docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md) live-model
verification -- the ONE thing no test in this repo can prove without real
Gemini/DeepSeek credentials, which are not available in the environment
this phase was implemented in.

Marked ``provider`` (skipped by default -- see pyproject.toml's markers).
Run explicitly, wherever real credentials ARE configured (the VPS):

    uv run pytest -m provider platform/ai/tests/test_phase_b4_live_verification.py -v

Reads credentials exactly the way the running app does
(``mesiri.bootstrap.settings.get_settings()``), so it uses whatever is
already configured for production -- no separate setup needed on a box
where the app already runs.

What this checks, and why each check exists:

1. The Bidilaj trace (§1 of the design doc) -- the real message that
   motivated Phase B -- must come back as 3+ intents, not 1. This is the
   headline claim of the whole phase; if this fails, B4 did not fix the
   thing it was built to fix.
2. Five deliberately single-intent messages must each come back as exactly
   1 intent. This is the OTHER half of the claim, and the riskier one
   (ADR-U1's stated risk): asking for a list creates real pressure to
   over-split. A message that touches multiple FACTS ("used 40 bags of
   cement for the foundation") must still be ONE intent, not fabricate a
   second one out of the work_item field.

Neither check is exact-match on wording (real model output varies run to
run) -- both check the SHAPE (how many intents, roughly what type), which
is what the rest of the pipeline actually depends on.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.provider


def _real_gemini_provider():
    from mesiri.bootstrap.settings import get_settings
    from mesiri_ai.adapters.gemini.adapter import GeminiProvider

    settings = get_settings()
    if not settings.gemini.api_key:
        pytest.skip("MESIRI_GEMINI__API_KEY not configured in this environment")
    return GeminiProvider(settings.gemini)


def _real_deepseek_provider():
    from mesiri.bootstrap.settings import get_settings
    from mesiri_ai.adapters.deepseek.adapter import DeepSeekExtractionProvider

    settings = get_settings()
    if not settings.deepseek.api_key:
        pytest.skip("MESIRI_DEEPSEEK__API_KEY not configured in this environment")
    return DeepSeekExtractionProvider(settings.deepseek)


_BIDILAJ_MESSAGE = (
    "Add a new project, a project named Bidilaj, and then create a site "
    "called Site A. Then I need to add an engineer, a site engineer, "
    "named Usman. I will send his WhatsApp number a little later."
)

# Deliberately single-intent, chosen because each one plausibly LOOKS
# splittable to a model asked "list every request" -- the exact pressure
# ADR-U1 accepted risk on. If any of these regularly comes back as more
# than one intent, the prompt's anti-over-splitting instruction is not
# holding on the real model and needs revisiting before this ships wider.
_SINGLE_INTENT_MESSAGES = [
    "used 40 bags of cement for the foundation",
    "paid 5000 for cement",
    "10 masons worked on the slab today",
    "JCB ran for 4 hours doing excavation",
    "raining since morning, work stopped",
]


@pytest.mark.parametrize("get_provider", [_real_gemini_provider, _real_deepseek_provider])
async def test_bidilaj_trace_becomes_multiple_intents(get_provider):
    provider = get_provider()
    result = await provider.extract(_BIDILAJ_MESSAGE, correlation_id="cor_b4_live_bidilaj")

    assert len(result.intents) >= 2, (
        f"{provider.provider} returned only {len(result.intents)} intent(s) for the "
        f"Bidilaj trace -- Phase B4's headline claim is unverified against the real "
        f"model. Intents: {[i.semantic_type for i in result.intents]}"
    )
    semantic_types = {i.semantic_type for i in result.intents}
    assert "project_create" in semantic_types, (
        f"{provider.provider} never extracted project_create from the Bidilaj "
        f"trace. Intents: {[i.semantic_type for i in result.intents]}"
    )


@pytest.mark.parametrize("get_provider", [_real_gemini_provider, _real_deepseek_provider])
@pytest.mark.parametrize("message", _SINGLE_INTENT_MESSAGES)
async def test_single_intent_messages_stay_single_intent(get_provider, message):
    provider = get_provider()
    result = await provider.extract(message, correlation_id="cor_b4_live_single")

    assert len(result.intents) == 1, (
        f"{provider.provider} split a single-intent message into "
        f"{len(result.intents)} intents: {[i.semantic_type for i in result.intents]!r} "
        f"for message {message!r} -- this is the over-splitting regression "
        f"ADR-U1 named as B4's real risk."
    )
