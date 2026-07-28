"""Correcting a misread name before the attendance is confirmed.

OCR and speech will never read every sheet perfectly, and before this a
single wrong name meant redoing the whole report. The parse is deterministic
rather than AI-classified -- see interactions/name_corrections.py for why.

Two halves are covered here: what counts as a correction, and what the
workflow does with one. The second is the load-bearing half -- a corrected
name has to go back through matching, not inherit the decision made about
the old spelling.
"""

from __future__ import annotations

import pytest

from interactions.name_corrections import parse_name_corrections
from workflows.labour_update.nodes import NAME_CORRECTIONS_FIELD, match_workers

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
AKHILESH_ID = "55555555-5555-4555-8555-555555555555"


# ---------------------------------------------------------------------------
# What counts as a correction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "Akhil -> Akhilesh",
        "Akhil --> Akhilesh",
        "Akhil => Akhilesh",
        "Akhil → Akhilesh",
        "Akhil = Akhilesh",
        "Akhil=Akhilesh",
        "  Akhil   ->   Akhilesh  ",
        "- Akhil -> Akhilesh",
    ],
)
def test_a_single_correction_is_understood_however_it_is_written(reply):
    assert parse_name_corrections(reply) == {"Akhil": "Akhilesh"}


def test_several_corrections_in_one_reply():
    """The whole point: two or three names are wrong at once, and the
    supervisor fixes them in one message rather than three round trips."""
    reply = "Correct:\nAkhil -> Akhilesh\nNiyas -> Niyas PM\nRahul -> Rahul Kumar"

    assert parse_name_corrections(reply) == {
        "Akhil": "Akhilesh",
        "Niyas": "Niyas PM",
        "Rahul": "Rahul Kumar",
    }


def test_corrections_separated_by_commas_on_one_line():
    assert parse_name_corrections("Akhil=Akhilesh, Niyas=Niyas PM") == {
        "Akhil": "Akhilesh",
        "Niyas": "Niyas PM",
    }


@pytest.mark.parametrize(
    "reply",
    [
        "yes",
        "save all",
        "12 helpers 4 masons",
        "Note: Akhil worked late",  # a colon is not a separator
        "Ravi-Kumar mason",  # a hyphen inside a name is not an arrow
        "Akhil -> Akhil",  # a no-op is noise, not an instruction
        "",
        "   ",
    ],
)
def test_a_reply_that_is_not_a_correction_is_not_claimed(reply):
    """This runs before confirmation handling, so a false positive would
    swallow a plain "yes" and leave the report unconfirmed."""
    assert parse_name_corrections(reply) == {}


def test_a_sentence_containing_an_arrow_is_not_a_name():
    """Names are short. A paragraph with an arrow in it must not end up in
    the register as somebody's name."""
    long_reply = "x" * 80 + " -> " + "y" * 80
    assert parse_name_corrections(long_reply) == {}


# ---------------------------------------------------------------------------
# What the workflow does with one
# ---------------------------------------------------------------------------


def _state(fields: dict, **extra) -> dict:
    state = {
        "workflow_instance_id": "wf_1",
        "workflow_key": "labour.attendance",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }
    state.update(extra)
    return state


def test_a_correction_renames_the_line_and_leaves_others_alone():
    update = match_workers(
        _state(
            {
                "lines": [
                    {"worker_name": "Akhil", "trade": "mason", "headcount": 1},
                    {"worker_name": "Rahul", "trade": "painter", "headcount": 1},
                    {"worker_name": None, "trade": "helper", "headcount": 12},
                ],
                NAME_CORRECTIONS_FIELD: {"Akhil": "Akhilesh"},
            }
        )
    )

    names = [line.get("worker_name") for line in update["collected_fields"]["lines"]]
    assert names == ["Akhilesh", "Rahul", None]


def test_correcting_a_name_re_runs_matching_against_the_register():
    """The reason a correction cannot be a simple string replace: "Akhil"
    matched nobody, but "Akhilesh" is on the register. Matching has to run
    again or the correction fixes the spelling and loses the worker."""
    update = match_workers(
        _state(
            {
                "lines": [{"worker_name": "Akhil", "trade": "mason", "headcount": 1}],
                "worker_candidates": [
                    {"worker_id": AKHILESH_ID, "name": "Akhilesh", "trade": "mason"}
                ],
                NAME_CORRECTIONS_FIELD: {"Akhil": "Akhilesh"},
            }
        )
    )

    line = update["collected_fields"]["lines"][0]
    assert line["worker_name"] == "Akhilesh"
    assert line["worker_id"] == AKHILESH_ID


def test_a_correction_discards_the_decision_made_about_the_old_name():
    """A decision recorded against the old spelling is exactly what the user
    is saying was wrong. Carrying it over would leave "Akhilesh" linked to
    whoever "Akhil" resolved to -- the silent false merge P4 exists to stop."""
    wrong_worker = "99999999-9999-4999-8999-999999999999"
    update = match_workers(
        _state(
            {
                "lines": [
                    {
                        "worker_name": "Akhil",
                        "trade": "mason",
                        "headcount": 1,
                        "worker_id": wrong_worker,
                        "worker_match_resolved": True,
                    }
                ],
                NAME_CORRECTIONS_FIELD: {"Akhil": "Akhilesh"},
            }
        )
    )

    line = update["collected_fields"]["lines"][0]
    assert line["worker_name"] == "Akhilesh"
    assert line["worker_id"] != wrong_worker


def test_the_correction_instruction_is_not_left_on_the_draft():
    """Bookkeeping, not attendance data -- it must not survive into the
    command or a later pass would re-apply it."""
    update = match_workers(
        _state(
            {
                "lines": [{"worker_name": "Akhil", "trade": "mason", "headcount": 1}],
                NAME_CORRECTIONS_FIELD: {"Akhil": "Akhilesh"},
            }
        )
    )

    assert NAME_CORRECTIONS_FIELD not in update["collected_fields"]


def test_correcting_a_name_nobody_reported_changes_nothing():
    """A typo in the correction itself must not invent a worker."""
    update = match_workers(
        _state(
            {
                "lines": [{"worker_name": "Akhil", "trade": "mason", "headcount": 1}],
                NAME_CORRECTIONS_FIELD: {"Suresh": "Suresh Babu"},
            }
        )
    )

    assert update["collected_fields"]["lines"][0]["worker_name"] == "Akhil"


def test_the_name_is_matched_case_insensitively():
    """The correction is typed from what is on screen, which may be block
    capitals from an OCR read."""
    update = match_workers(
        _state(
            {
                "lines": [{"worker_name": "AKHIL", "trade": "mason", "headcount": 1}],
                NAME_CORRECTIONS_FIELD: {"akhil": "Akhilesh"},
            }
        )
    )

    assert update["collected_fields"]["lines"][0]["worker_name"] == "Akhilesh"
