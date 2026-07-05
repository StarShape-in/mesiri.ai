"""Unit tests for the live WhatsApp sender-identity helpers (no DB)."""

from __future__ import annotations

from types import SimpleNamespace

from context.live_identity import (
    ProjectRef,
    SenderContext,
    _digits,
    context_header,
    pick_project,
)


def _und(*candidate_fields: dict):
    return SimpleNamespace(
        candidates=[SimpleNamespace(fields=f, unknown_fields={}) for f in candidate_fields]
    )


def test_digits_normalizes_phone_formats():
    assert _digits("+91 98765 43210") == "919876543210"
    assert _digits("919876543210") == "919876543210"
    assert _digits("(0)98-765") == "098765"
    assert _digits(None) == ""


def test_pick_project_single_project_autoselected():
    projects = [ProjectRef("p1", "Skyline Towers")]
    assert pick_project(_und(), projects) == projects[0]


def test_pick_project_none_when_multiple_and_unspecified():
    projects = [ProjectRef("p1", "Skyline Towers"), ProjectRef("p2", "Green Valley")]
    assert pick_project(_und({"equipment_name": "JCB"}), projects) is None


def test_pick_project_matches_named_project_case_insensitive():
    projects = [ProjectRef("p1", "Skyline Towers"), ProjectRef("p2", "Green Valley")]
    got = pick_project(_und({"project_name": "green valley"}), projects)
    assert got is not None and got.id == "p2"


def test_pick_project_ignores_unauthorized_name():
    projects = [ProjectRef("p1", "Skyline Towers"), ProjectRef("p2", "Green Valley")]
    # Names a project the user has no access to -> not auto-picked (stays None).
    assert pick_project(_und({"project_name": "Marina Tower"}), projects) is None


def test_context_header_variants():
    ctx = SenderContext("u1", "Ravi", "SITE_ENGINEER", "o1", "Superman Company", True,
                        [ProjectRef("p1", "Skyline Towers")])
    assert "Ravi" in context_header(ctx, ctx.projects[0])
    assert "Skyline Towers" in context_header(ctx, ctx.projects[0])
    multi = SenderContext("u1", "Ravi", "ADMIN", "o1", "Superman Company", True,
                          [ProjectRef("p1", "A"), ProjectRef("p2", "B")])
    assert "project unspecified" in context_header(multi, None)
