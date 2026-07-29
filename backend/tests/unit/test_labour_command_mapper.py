"""ConfirmedActionV2 -> RecordLabourAttendanceCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mesiri.application.labour.mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"
USR = "22222222-2222-4222-8222-222222222222"
RAVI_KUMAR = "55555555-5555-4555-8555-555555555555"


def _confirmed(fields: dict, *, project_id=PRJ) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.RECORD_LABOUR_ATTENDANCE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=SITE,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def _line(**kwargs) -> dict:
    base = {"worker_name": None, "trade": "helper", "headcount": 1}
    base.update(kwargs)
    return base


def test_named_and_headcount_lines_both_map():
    cmd = build_command(
        _confirmed(
            {
                "lines": [
                    _line(worker_name="Ravi", trade="mason", headcount=1, daily_wage="800"),
                    _line(worker_name=None, trade="helper", headcount=12),
                ]
            }
        )
    )
    assert len(cmd.lines) == 2
    assert cmd.lines[0].worker_name == "Ravi"
    assert cmd.lines[0].daily_wage == Decimal("800")
    assert cmd.lines[1].worker_name is None
    assert cmd.lines[1].headcount == 12


def test_a_resolved_worker_id_is_carried_through_as_a_real_uuid():
    """The P4 payoff: a line matching_workers already resolved reaches the
    command carrying the register link, typed and validated."""
    cmd = build_command(
        _confirmed({"lines": [_line(worker_name="Ravi", worker_id=RAVI_KUMAR)]})
    )
    assert cmd.lines[0].worker_id == RAVI_KUMAR


def test_a_temporary_worker_has_no_worker_id():
    """P1: nothing here ever invents or fills in a worker_id."""
    cmd = build_command(_confirmed({"lines": [_line(worker_name="Vinod", worker_id=None)]}))
    assert cmd.lines[0].worker_id is None


def test_the_original_script_survives_transliteration():
    cmd = build_command(
        _confirmed(
            {"lines": [_line(worker_name="Ravi", worker_name_original="രവി")]}
        )
    )
    assert cmd.lines[0].worker_name_original == "രവി"


def test_a_missing_wage_stays_none_not_zero():
    """P9: a wage-less report is a legitimate fast capture. Unlike materials'
    quantity (which defaults to zero, an obviously-invalid value validation
    catches), a missing wage must not be silently invented as a real number."""
    cmd = build_command(_confirmed({"lines": [_line(daily_wage=None)]}))
    assert cmd.lines[0].daily_wage is None


def test_junk_headcount_falls_back_to_one_rather_than_crashing():
    cmd = build_command(_confirmed({"lines": [_line(headcount="not a number")]}))
    assert cmd.lines[0].headcount == 1


def test_malformed_lines_are_skipped_not_fatal():
    """Fields have already survived a JSON round-trip through
    workflow_instances by the time they reach the mapper; a stray string or
    None in the list must not take down the whole command."""
    cmd = build_command(_confirmed({"lines": ["not a dict", None, _line(trade="mason")]}))
    assert len(cmd.lines) == 1
    assert cmd.lines[0].trade == "mason"


def test_missing_lines_key_produces_an_empty_command_not_a_crash():
    """domains/workforce/validation.py rejects this; the mapper's job is only
    to build a well-typed command, valid or not."""
    cmd = build_command(_confirmed({}))
    assert cmd.lines == []


def test_idempotency_key_is_workflow_instance_id_not_confirmed_action_id():
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.idempotency_key == "wf_1"
    assert cmd.idempotency_key != "conf_1"


def test_scope_denormalized_from_draft_action():
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.organization_id == ORG
    assert cmd.project_id == PRJ
    assert cmd.site_id == SITE
    assert cmd.created_by == USR


def test_project_id_none_is_preserved_not_invented():
    """Domain validation rejects a missing project_id; the mapper must never
    invent one, mirroring materials' identical guarantee."""
    cmd = build_command(_confirmed({"lines": [_line()]}, project_id=None))
    assert cmd.project_id is None


def test_the_date_decided_upstream_is_used_not_overwritten():
    """The bug this closes: the mapper used to stamp date.today() over
    whatever the message said, so "yesterday 12 masons worked" was filed
    under today. Canonicalization now owns the decision -- it is the only
    point holding both the message and the sender's timezone."""
    cmd = build_command(
        _confirmed(
            {
                "lines": [_line()],
                "occurred_date": "2026-07-20",
                "occurred_date_source": "stated_by_user",
            }
        )
    )
    assert cmd.occurred_date == date(2026, 7, 20)
    assert cmd.occurred_date_source == "stated_by_user"


def test_occurred_date_defaults_to_today_when_a_draft_predates_dating():
    """An older draft, persisted at AWAITING_CONFIRMATION before this shipped,
    must stay confirmable rather than failing on a field it never carried."""
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.occurred_date == date.today()
    assert cmd.occurred_date_source == "inferred_at_confirmation"


def test_a_corrupt_stored_date_falls_back_rather_than_failing_the_save():
    """The user already confirmed; losing the whole record over an unparseable
    date field would be worse than recording it dated today."""
    cmd = build_command(_confirmed({"lines": [_line()], "occurred_date": "not-a-date"}))
    assert cmd.occurred_date == date.today()


def test_recorded_via_is_carried_through():
    cmd = build_command(_confirmed({"lines": [_line()], "recorded_via": "whatsapp_voice"}))
    assert cmd.recorded_via == "whatsapp_voice"


def test_recorded_via_defaults_to_whatsapp_text_when_absent():
    """A corrected/replayed draft, or any path that skipped canonicalization's
    modality mapping, still produces a valid, non-fabricated default rather
    than a missing required field."""
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.recorded_via == "whatsapp_text"


def test_notes_are_carried_through():
    cmd = build_command(_confirmed({"lines": [_line()], "notes": "rained after lunch"}))
    assert cmd.notes == "rained after lunch"


def test_a_single_media_object_key_becomes_one_attachment():
    """What the pipeline actually populates today (singular), wrapped rather
    than dropped -- see mapper.py's _attachment_object_keys docstring."""
    cmd = build_command(
        _confirmed({"lines": [_line()], "media_object_key": "media/wamid.1/sheet.jpg"})
    )
    assert cmd.attachment_object_keys == ["media/wamid.1/sheet.jpg"]


def test_a_real_attachment_list_wins_over_the_singular_key():
    cmd = build_command(
        _confirmed(
            {
                "lines": [_line()],
                "attachment_object_keys": ["a.jpg", "b.jpg"],
                "media_object_key": "ignored.jpg",
            }
        )
    )
    assert cmd.attachment_object_keys == ["a.jpg", "b.jpg"]


def test_no_photo_means_no_attachments():
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.attachment_object_keys == []


# --- Supersede: the writer migration 0371 was waiting for -------------------

def test_corrects_report_id_reaches_the_command_when_the_user_chose_replace():
    """The read side has always excluded a corrected report from every total;
    until this was threaded through, nothing ever set it, so the guard could
    not fire. Production shows 14 reports for one site-day, all counting."""
    report_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    cmd = build_command(_confirmed({"lines": [_line()], "corrects_report_id": report_id}))
    assert cmd.corrects_report_id == report_id


def test_an_ordinary_report_corrects_nothing():
    """Absent is the common case and must stay None -- a second shift on the
    same day is a separate report, not a correction of the first."""
    cmd = build_command(_confirmed({"lines": [_line()]}))
    assert cmd.corrects_report_id is None


def test_a_blank_correction_id_is_treated_as_absent_not_as_an_id():
    """Fields survive a JSON round-trip through workflow_instances, where an
    unanswered slot can come back as "" rather than missing. "" would fail the
    command's UUID validation for a reason no user could act on."""
    for blank in ("", "   ", None):
        cmd = build_command(_confirmed({"lines": [_line()], "corrects_report_id": blank}))
        assert cmd.corrects_report_id is None
