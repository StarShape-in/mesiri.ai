"""ExtractionResult's Phase B migration (docs/execution/
UNIFIED_UNDERSTANDING_PIPELINE.md, ADR-U1): semantic_type/fields/etc. are now
derived properties reading intents[0], not real fields -- and the legacy
top-level constructor kwargs (ExtractionResult(semantic_type=..., fields=
...)) must keep working unchanged, since ~100+ existing call sites across
the monorepo (adapters, fakes, test fixtures) still construct results that
way and are not migrated until Phase B5.
"""

from __future__ import annotations

from mesiri_ai.models import ExtractedIntent, ExtractionResult, parse_extracted_intents


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


# ---------------------------------------------------------------------------
# parse_extracted_intents (Phase B4): the shared parser every adapter's
# extract()/understand_voice() calls to turn a provider's raw "intents" JSON
# array into list[ExtractedIntent]. Fakes only -- no live provider call.
# ---------------------------------------------------------------------------


def test_parses_a_single_intent_the_common_case():
    raw = [
        {
            "semantic_type": "expense",
            "fields": {"amount": 500},
            "missing_fields": [],
            "field_confidences": {"amount": 0.9},
        }
    ]
    intents = parse_extracted_intents(raw)
    assert len(intents) == 1
    assert intents[0].semantic_type == "expense"
    assert intents[0].fields == {"amount": 500}
    assert intents[0].field_confidences == {"amount": 0.9}


def test_parses_the_bidilaj_trace_three_real_intents():
    raw = [
        {"semantic_type": "project_create", "fields": {"name": "Bidilaj"}},
        {"semantic_type": "site_create", "fields": {"name": "Site A"}},
        {
            "semantic_type": "add_project_member",
            "fields": {"member_name": "Usman", "role": "site_engineer"},
        },
    ]
    intents = parse_extracted_intents(raw)
    assert len(intents) == 3
    assert [i.semantic_type for i in intents] == [
        "project_create",
        "site_create",
        "add_project_member",
    ]


def test_missing_intents_key_returns_an_empty_list():
    """Falls through to ExtractionResult's own _normalize (one default
    unknown intent) when constructed -- this function itself just returns
    empty, it does not normalize."""
    assert parse_extracted_intents(None) == []


def test_non_list_intents_value_returns_an_empty_list():
    """A provider hallucinating intents as a bare object rather than an
    array must degrade safely, not raise."""
    assert parse_extracted_intents({"semantic_type": "expense"}) == []


def test_a_malformed_entry_among_good_ones_is_skipped_not_fatal():
    """One bad entry (not a dict -- e.g. a stray string) must not sink the
    other, valid intents in the same response."""
    raw = [
        {"semantic_type": "project_create", "fields": {"name": "Bidilaj"}},
        "not a dict",
        {"semantic_type": "site_create", "fields": {"name": "Site A"}},
    ]
    intents = parse_extracted_intents(raw)
    assert len(intents) == 2
    assert intents[0].semantic_type == "project_create"
    assert intents[1].semantic_type == "site_create"


def test_missing_optional_keys_on_one_entry_default_sensibly():
    raw = [{"semantic_type": "expense"}]
    intents = parse_extracted_intents(raw)
    assert intents[0].fields == {}
    assert intents[0].missing_fields == []
    assert intents[0].field_confidences == {}


def test_field_confidences_are_coerced_to_float():
    """Some providers may return confidence as a JSON int/string-shaped
    number -- must not crash the parser."""
    raw = [{"semantic_type": "expense", "field_confidences": {"amount": 1}}]
    intents = parse_extracted_intents(raw)
    assert intents[0].field_confidences == {"amount": 1.0}
    assert isinstance(intents[0].field_confidences["amount"], float)
