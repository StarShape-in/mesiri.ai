"""Which day is a report about?

Two bugs are being pinned here, and both were silent — the record looked
perfectly normal, just dated wrong, and attendance is append-only so nobody
could correct it afterwards.

1. A stated date was ignored. "yesterday 12 masons worked" was filed under
   today.
2. "Today" meant the *server's* today. The host runs UTC; a site in India is
   UTC+5:30, so every report between midnight and 05:30 local landed on the
   previous day. Early starts are normal on site, so that window is real.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from canonicalization.occurred_date import (
    OCCURRED_DATE_FIELD,
    OCCURRED_DATE_SOURCE_FIELD,
    SOURCE_INFERRED,
    SOURCE_STATED,
    parse_stated_date,
    resolve_occurred_date,
    today_for,
)

TODAY = datetime.date(2026, 7, 27)


# --- reading what the user said --------------------------------------------


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("yesterday", datetime.date(2026, 7, 26)),
        ("Yesterday", datetime.date(2026, 7, 26)),
        ("yday", datetime.date(2026, 7, 26)),
        ("day before yesterday", datetime.date(2026, 7, 25)),
        ("today", TODAY),
        ("2026-07-20", datetime.date(2026, 7, 20)),
    ],
)
def test_a_stated_day_is_understood(said, expected):
    assert parse_stated_date(said, today=TODAY) == expected


@pytest.mark.parametrize("said", ["Friday", "last week", "sometime", "", None, "not-a-date"])
def test_an_ambiguous_day_is_refused_rather_than_guessed(said):
    """Half-understanding a date is worse than admitting the assumption: a
    bare weekday could be six different dates, and the fallback at least
    announces itself as a guess at confirmation."""
    assert parse_stated_date(said, today=TODAY) is None


@pytest.mark.parametrize("said", ["tomorrow", "2026-12-31"])
def test_a_future_day_is_refused(said):
    """A report records work already done. A date after today is a misread,
    and filing work in the future would quietly break every "today" and "this
    week" total."""
    assert parse_stated_date(said, today=TODAY) is None


def test_an_impossible_date_is_refused():
    assert parse_stated_date("2026-02-30", today=TODAY) is None


def test_a_real_date_object_passes_through():
    assert parse_stated_date(datetime.date(2026, 7, 1), today=TODAY) == datetime.date(2026, 7, 1)


# --- whose "today"? --------------------------------------------------------


def test_today_is_the_senders_today_not_the_servers():
    """The bug: at 01:00 in India the server (UTC) still believes it is
    yesterday, so an early-morning attendance was filed under the wrong day."""
    india_early_morning = datetime.datetime(2026, 7, 27, 1, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert india_early_morning.astimezone(datetime.UTC).date() == datetime.date(2026, 7, 26)

    with patch("canonicalization.occurred_date.datetime") as mock_dt:
        mock_dt.datetime.now.side_effect = lambda tz=None: india_early_morning.astimezone(tz)
        mock_dt.date = datetime.date
        assert today_for("Asia/Kolkata") == datetime.date(2026, 7, 27)


def test_an_unknown_timezone_falls_back_instead_of_raising():
    """Not knowing where someone is must never stop them recording work."""
    assert today_for("Not/AZone") == datetime.date.today()
    assert today_for(None) == datetime.date.today()


# --- what ends up on the record --------------------------------------------


def _resolved(fields: dict, tz: str | None = "Asia/Kolkata") -> dict:
    return resolve_occurred_date(fields, timezone_name=tz)


def test_a_stated_date_is_recorded_as_stated():
    out = _resolved({"occurred_on": "2026-07-20"})
    assert out[OCCURRED_DATE_FIELD] == "2026-07-20"
    assert out[OCCURRED_DATE_SOURCE_FIELD] == SOURCE_STATED


def test_no_stated_date_falls_back_to_today_and_says_so():
    out = _resolved({})
    assert out[OCCURRED_DATE_FIELD] == today_for("Asia/Kolkata").isoformat()
    assert out[OCCURRED_DATE_SOURCE_FIELD] == SOURCE_INFERRED


def test_an_unparseable_stated_date_is_treated_as_no_date():
    """Falls back AND admits it, rather than silently keeping a guess."""
    out = _resolved({"occurred_on": "Friday"})
    assert out[OCCURRED_DATE_SOURCE_FIELD] == SOURCE_INFERRED


def test_the_raw_extracted_value_does_not_survive_alongside_the_date():
    """Leaving `occurred_on` behind would render it as its own line in the
    confirmation next to the date it produced -- the same duplication the
    material alias-popping already guards against."""
    assert "occurred_on" not in _resolved({"occurred_on": "yesterday"})


def test_both_fields_are_always_set():
    """Downstream never has to decide what a missing date means."""
    for fields in ({}, {"occurred_on": "yesterday"}, {"occurred_on": "rubbish"}):
        out = _resolved(fields)
        assert OCCURRED_DATE_FIELD in out
        assert OCCURRED_DATE_SOURCE_FIELD in out


def test_other_fields_are_left_untouched():
    out = _resolved({"lines": [{"worker_name": "Ravi"}], "notes": "all good"})
    assert out["lines"] == [{"worker_name": "Ravi"}]
    assert out["notes"] == "all good"
