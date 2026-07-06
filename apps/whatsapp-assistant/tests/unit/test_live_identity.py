"""Unit tests for the live WhatsApp sender-identity helpers (no DB)."""

from __future__ import annotations

from types import SimpleNamespace

from context.live_identity import (
    NO_ORG_MESSAGE,
    ProjectRef,
    SenderContext,
    _digits,
    context_header,
    pick_project,
    whoami_reply,
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


def test_whoami_reply_includes_role_org_projects():
    ctx = SenderContext(
        "u1", "Alan", "ADMIN", "o1", "superman company", True,
        [
            ProjectRef("p1", "Skyline Towers", location="North Zone",
                       code="SKY-01", status="critical", progress=68, open_issues=3),
            ProjectRef("p2", "Green Valley", location="East Zone",
                       status="at_risk", progress=42, open_issues=1),
        ],
    )
    reply = whoami_reply(ctx)
    assert "Alan" in reply
    assert "Admin" in reply           # role pretty-printed
    assert "superman company" in reply
    assert "Skyline Towers" in reply
    assert "North Zone" in reply
    assert "Green Valley" in reply
    assert "(2)" in reply             # project count


def test_whoami_reply_handles_no_projects():
    ctx = SenderContext("u1", "Alan", "USER", "o1", "Empty Co", True, [])
    reply = whoami_reply(ctx)
    assert "none assigned" in reply.lower()


def test_no_org_message_is_distinct_from_unregistered():
    # The two cases must read differently so the recipient understands the gap.
    assert "isn't registered" in __import__("context.live_identity", fromlist=["UNREGISTERED_MESSAGE"]).UNREGISTERED_MESSAGE.lower()
    assert "not part of any organization" in NO_ORG_MESSAGE.format(name="Alan").lower()
    assert "Alan" in NO_ORG_MESSAGE.format(name="Alan")
