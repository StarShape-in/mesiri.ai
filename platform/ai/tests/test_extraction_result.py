"""ExtractionResult's Phase B migration (docs/execution/
UNIFIED_UNDERSTANDING_PIPELINE.md, ADR-U1): semantic_type/fields/etc. are now
derived properties reading intents[0], not real fields -- and the legacy
top-level constructor kwargs (ExtractionResult(semantic_type=..., fields=
...)) must keep working unchanged, since ~100+ existing call sites across
the monorepo (adapters, fakes, test fixtures) still construct results that
way and are not migrated until Phase B5.
"""

from __future__ import annotations

from mesiri_ai.models import ExtractedIntent, ExtractionResult


def test_legacy_kwargs_still_construct_a_single_intent():
    """The exact pre-Phase-B constructor shape -- must keep working
    unmodified, since nothing outside this test file has been migrated to
    intents=[...] directly yet (that's Phase B5)."""
    result = ExtractionResult(
        semantic_type="expense",
        fields={"amount": 500, "vendor": "ABC Hardware"},
        provider="fake",
    )
    assert result.semantic_type == "expense"
    assert result.fields == {"amount": 500, "vendor": "ABC Hardware"}
    assert len(result.intents) == 1
    assert result.intents[0].semantic_type == "expense"
    assert result.intents[0].fields == {"amount": 500, "vendor": "ABC Hardware"}
    assert result.provider == "fake"


def test_bare_construction_normalizes_to_one_default_intent():
    """ExtractionResult() with no args at all is a real, existing pattern
    (FakeExtractionProvider's own default) -- "no intents" must never be
    representable, same invariant DecompositionResult's own _normalize
    enforces for its analogous empty case."""
    result = ExtractionResult()
    assert len(result.intents) == 1
    assert result.semantic_type == "unknown"
    assert result.fields == {}


def test_new_style_intents_construction_is_untouched_by_the_legacy_migration():
    """Constructing with intents=[...] directly (the new, Phase-B-native
    shape) must not also try to migrate legacy kwargs -- there are none to
    migrate, and the derived properties must read the SUPPLIED intents."""
    result = ExtractionResult(
        intents=[
            ExtractedIntent(semantic_type="project_create", fields={"name": "Bidilaj"}),
            ExtractedIntent(semantic_type="site_create", fields={"name": "Site A"}),
        ]
    )
    assert len(result.intents) == 2
    # Derived properties read intents[0] only -- callers that need the rest
    # read .intents directly (Phase B5's whole point).
    assert result.semantic_type == "project_create"
    assert result.fields == {"name": "Bidilaj"}
    assert result.intents[1].semantic_type == "site_create"


def test_all_derived_properties_read_intents_zero():
    result = ExtractionResult(
        semantic_type="material_update",
        fields={"material_name": "cement"},
        unknown_fields={"batch_no": "X1"},
        missing_fields=["quantity"],
        field_confidences={"material_name": 0.9},
        warnings=["low confidence on unit"],
    )
    assert result.unknown_fields == {"batch_no": "X1"}
    assert result.missing_fields == ["quantity"]
    assert result.field_confidences == {"material_name": 0.9}
    assert result.warnings == ["low confidence on unit"]


def test_message_level_fields_are_unaffected_by_the_intent_migration():
    """detected_language/transcript/translated_text/provider/model/
    latency_ms are message-level, not per-intent -- never touched by the
    legacy-kwargs migrator (they aren't in _INTENT_KWARGS)."""
    result = ExtractionResult(
        semantic_type="expense",
        fields={"amount": 500},
        detected_language="ml",
        transcript="original voice text",
        translated_text="translated text",
        provider="gemini",
        model="gemini-2.0",
        latency_ms=123.4,
    )
    assert result.detected_language == "ml"
    assert result.transcript == "original voice text"
    assert result.translated_text == "translated text"
    assert result.provider == "gemini"
    assert result.model == "gemini-2.0"
    assert result.latency_ms == 123.4
    assert result.semantic_type == "expense"


def test_multiple_intents_the_bidilaj_trace_shape():
    """The real trace that motivated Phase B (docs/execution/
    UNIFIED_UNDERSTANDING_PIPELINE.md §1): one message, three intents."""
    result = ExtractionResult(
        intents=[
            ExtractedIntent(semantic_type="project_create", fields={"name": "Bidilaj"}),
            ExtractedIntent(semantic_type="site_create", fields={"name": "Site A"}),
            ExtractedIntent(
                semantic_type="add_project_member",
                fields={"member_name": "Usman", "role": "site_engineer"},
            ),
        ],
        provider="fake",
    )
    assert len(result.intents) == 3
    assert [i.semantic_type for i in result.intents] == [
        "project_create",
        "site_create",
        "add_project_member",
    ]
    # events[0]-style callers (not yet migrated) still see a coherent
    # single answer -- the first intent, not a crash or an empty result.
    assert result.semantic_type == "project_create"
    assert result.fields == {"name": "Bidilaj"}
