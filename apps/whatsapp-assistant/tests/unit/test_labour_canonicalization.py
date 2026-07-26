"""Labour canonicalization — turning whatever the AI returned into `lines`.

This is the seam the whole Labour workflow depends on: `workflows/labour_update`
reads exactly one field, `lines`, where each entry is either a named person or
an anonymous headcount group (Labour plan principle P10). Everything an
extraction provider might plausibly hand back has to arrive in that one shape,
because the alternative is teaching the graph three input dialects.

Kept separate from test_canonicalization.py, which is already long and covers
the material/finance aliasing.
"""

from __future__ import annotations

from canonicalization import build_canonical_event
from mesiri_contracts.assistant.candidates import LabourUpdateCandidate
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _context() -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="org_1",
        context_user_id="usr_1",
        context_project_id="prj_1",
        context_site_id="site_1",
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )


def _event(fields: dict, *, modality: InputModality = InputModality.TEXT, media: str | None = None):
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=modality,
        semantic_type=SemanticType.LABOUR_UPDATE,
        candidates=[LabourUpdateCandidate(fields=fields)],
        overall_confidence=ConfidenceLevel.HIGH,
        original_content_reference=media,
    )
    return build_canonical_event(understanding, _context())


def _lines(fields: dict) -> list[dict]:
    return _event(fields).fields["lines"]


# --- the shape the extraction prompt now asks for -------------------------


def test_named_workers_become_one_line_each():
    lines = _lines(
        {
            "workers": [
                {"name": "Ravi", "trade": "mason", "headcount": 1},
                {"name": "Arun", "trade": "painter", "headcount": 1},
            ]
        }
    )
    assert [line["worker_name"] for line in lines] == ["Ravi", "Arun"]
    assert [line["trade"] for line in lines] == ["mason", "painter"]
    assert [line["headcount"] for line in lines] == [1, 1]


def test_headcount_groups_carry_no_name():
    lines = _lines({"workers": [{"trade": "helper", "headcount": 12}]})
    assert lines[0]["worker_name"] is None
    assert lines[0]["headcount"] == 12


def test_named_and_headcount_lines_mix_in_one_report():
    """P10: "Ravi mason, Arun painter, 12 helpers, 4 carpenters" is one
    message, not two modes."""
    lines = _lines(
        {
            "workers": [
                {"name": "Ravi", "trade": "mason", "headcount": 1},
                {"name": "Arun", "trade": "painter", "headcount": 1},
                {"trade": "helper", "headcount": 12},
                {"trade": "carpenter", "headcount": 4},
            ]
        }
    )
    assert len(lines) == 4
    assert sum(line["headcount"] for line in lines) == 18
    assert [bool(line["worker_name"]) for line in lines] == [True, True, False, False]


def test_wage_is_carried_when_stated():
    lines = _lines({"workers": [{"name": "Ravi", "trade": "mason", "daily_wage": 800}]})
    assert lines[0]["daily_wage"] == 800


def test_wage_is_absent_when_not_stated():
    """P9: a wage-less report is a legitimate fast capture, not an error, and
    must not be filled in with a guess."""
    assert "daily_wage" not in _lines({"workers": [{"trade": "helper", "headcount": 6}]})[0]


# --- defending against what providers actually do -------------------------


def test_a_named_worker_is_always_one_person():
    """The dangerous misread: a provider that folds "Ravi" and "12 helpers"
    into `{"name": "Ravi", "headcount": 12}` would otherwise bill twelve days
    to one man. A name pins the count to 1."""
    assert _lines({"workers": [{"name": "Ravi", "headcount": 12}]})[0]["headcount"] == 1


def test_provider_key_aliases_are_accepted():
    lines = _lines({"workers": [{"worker_name": "Ravi", "role": "mason", "count": 1}]})
    assert lines[0]["worker_name"] == "Ravi"
    assert lines[0]["trade"] == "mason"


def test_bare_strings_are_kept_as_names_not_discarded():
    """Losing the only thing the user said is worse than an imperfect line."""
    lines = _lines({"workers": ["Ravi", "Arun"]})
    assert [line["worker_name"] for line in lines] == ["Ravi", "Arun"]


def test_empty_and_malformed_entries_are_skipped():
    lines = _lines({"workers": [{}, None, {"trade": "mason", "headcount": 3}]})
    assert len(lines) == 1
    assert lines[0]["trade"] == "mason"


def test_zero_or_junk_headcount_falls_back_to_one():
    assert _lines({"workers": [{"trade": "mason", "headcount": 0}]})[0]["headcount"] == 1
    assert _lines({"workers": [{"trade": "mason", "headcount": "many"}]})[0]["headcount"] == 1


def test_decimal_headcount_is_truncated_not_rejected():
    assert _lines({"workers": [{"trade": "helper", "headcount": 12.0}]})[0]["headcount"] == 12


# --- the older flat shape still works -------------------------------------


def test_flat_headcount_and_trade_become_a_single_group_line():
    """What the extraction prompt asked for until 2026-07-26, and what a
    provider still falls back to on a terse message. It must stay actionable
    rather than becoming unrecognized."""
    event = _event({"headcount": 12, "trade": "helper"})
    assert event.event_type is CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.fields["lines"] == [
        {"worker_name": None, "trade": "helper", "headcount": 12}
    ]


def test_already_canonical_lines_pass_through():
    """A corrected or replayed event arrives already in the final shape."""
    lines = _lines({"lines": [{"worker_name": "Ravi", "trade": "mason", "headcount": 1}]})
    assert lines[0]["worker_name"] == "Ravi"


# --- fields that must not leak into the confirmation ----------------------


def test_folded_flat_fields_do_not_also_survive_as_their_own_fields():
    """Leaving `headcount` beside the line it produced would show the same
    attendance twice in the confirmation text -- the bug
    _normalize_material_fields' alias-popping already guards against."""
    fields = _event({"headcount": 12, "trade": "helper"}).fields
    assert "headcount" not in fields
    assert "trade" not in fields
    assert "workers" not in fields


def test_report_level_contractor_is_pushed_down_to_each_line():
    """Stated once ("all from Kumar Team") but scored per worker by matching."""
    lines = _lines(
        {
            "contractor": "Kumar Team",
            "workers": [{"name": "Ravi", "trade": "mason"}, {"trade": "helper", "headcount": 5}],
        }
    )
    assert all(line["contractor"] == "Kumar Team" for line in lines)


def test_a_lines_own_contractor_wins_over_the_report_level_one():
    lines = _lines(
        {
            "contractor": "Kumar Team",
            "workers": [{"name": "Ravi", "contractor": "Self"}],
        }
    )
    assert lines[0]["contractor"] == "Self"


# --- routing and completeness ---------------------------------------------


def test_a_real_attendance_is_actionable_and_routes_to_labour():
    event = _event({"workers": [{"name": "Ravi", "trade": "mason"}]})
    assert event.event_type is CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED
    assert event.completeness is IntentCompleteness.ACTIONABLE
    assert event.missing_fields == []


def test_an_attendance_naming_and_counting_nobody_asks_for_clarification():
    event = _event({"contractor": "Kumar Team"})
    assert event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert event.completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "lines" in event.missing_fields


# --- text, voice and image all land in the same place ---------------------


def test_voice_and_image_produce_the_same_structure_as_text():
    """Definition-of-Done criterion 3: one structured result regardless of how
    the report arrived. Understanding transcribes voice and reads images
    upstream; by this point all three are the same extracted fields, and this
    pins that canonicalization adds no modality-specific behaviour."""
    fields = {"workers": [{"name": "Ravi", "trade": "mason", "headcount": 1}]}
    text = _event(fields, modality=InputModality.TEXT).fields["lines"]
    voice = _event(fields, modality=InputModality.VOICE).fields["lines"]
    image = _event(fields, modality=InputModality.IMAGE).fields["lines"]
    assert text == voice == image


def test_an_attendance_photo_is_carried_for_attachment():
    """ADR-L3: the sheet photo rides through on the generic media field, the
    same one receipts use, so it can be attached to the record later."""
    event = _event(
        {"workers": [{"trade": "helper", "headcount": 12}]},
        modality=InputModality.IMAGE,
        media="media/wamid.1/sheet.jpg",
    )
    assert event.fields["media_object_key"] == "media/wamid.1/sheet.jpg"
    assert event.completeness is IntentCompleteness.ACTIONABLE


# --- non-Latin scripts (Malayalam, Hindi, Tamil) --------------------------


def test_a_transliterated_name_keeps_the_original_spelling():
    """Names transliterate, they never translate -- a name is a person, not
    vocabulary. The original is kept so a wrong reading stays checkable
    against the paper sheet."""
    lines = _lines(
        {"workers": [{"name": "Ravi", "name_original": "രവി", "trade": "mason", "headcount": 1}]}
    )
    assert lines[0]["worker_name"] == "Ravi"
    assert lines[0]["worker_name_original"] == "രവി"


def test_latin_script_sheets_gain_no_extra_field():
    """No noise on the common case."""
    assert "worker_name_original" not in _lines({"workers": [{"name": "Ravi", "trade": "mason"}]})[0]


def test_an_original_identical_to_the_name_is_dropped():
    lines = _lines({"workers": [{"name": "Ravi", "name_original": "Ravi", "trade": "mason"}]})
    assert "worker_name_original" not in lines[0]


def test_the_alternative_original_key_is_accepted():
    lines = _lines({"workers": [{"name": "Suresh", "original_name": "സുരേഷ്"}]})
    assert lines[0]["worker_name_original"] == "സുരേഷ്"


def test_a_transliterated_group_row_still_carries_its_english_trade():
    """Trades DO translate: കൊത്തുപണിക്കാരൻ is genuinely "mason"."""
    lines = _lines({"workers": [{"trade": "mason", "headcount": 6}]})
    assert lines[0]["trade"] == "mason"
    assert lines[0]["worker_name"] is None
