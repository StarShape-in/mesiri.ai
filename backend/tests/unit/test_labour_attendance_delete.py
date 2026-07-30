"""Deleting attendance is off unless someone deliberately turned it on.

This endpoint contradicts the module's own rule that attendance is immutable
(plan principle P5) and exists only for clearing development data. The
dashboard a developer clicks it in is the same build customers use, so the
gates are what make it safe to ship at all: it answers for nobody unless
MESIRI_ALLOW_LABOUR_DELETE is set, and then only for ADMIN.

These pin the gates and the blast radius. A gate that silently failed open
would be far worse than no delete button.
"""

from __future__ import annotations

import ast
import inspect

from mesiri.bootstrap.settings import Settings
from mesiri.domains.workforce import router as workforce_router

_SOURCE = inspect.getsource(workforce_router.delete_attendance_report)


def _code_only(source: str, func_name: str) -> str:
    """The function's executable body, with the docstring stripped out.

    Needed because the docstring *says* "never touches workforce_workers", so a
    substring check against the whole source passes on the prose and proves
    nothing about the SQL. Asserting against a comment is worse than not
    asserting at all.
    """
    tree = ast.parse(source)
    func = next(n for n in tree.body if getattr(n, "name", None) == func_name)
    statements = [
        node
        for node in func.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    return "\n".join(ast.unparse(node) for node in statements)


_CODE = _code_only(_SOURCE, "delete_attendance_report")

# Both gates now live in one shared helper, so the endpoint body just calls it.
_GATE = _code_only(
    inspect.getsource(workforce_router._assert_may_delete_labour),
    "_assert_may_delete_labour",
)


# --- The gates -------------------------------------------------------------

def test_deletion_is_disabled_by_default():
    """Off unless explicitly enabled, so deploying the endpoint everywhere is
    safe. If this flips to True by default, production gains a delete button."""
    assert Settings().allow_labour_delete is False


def test_the_gate_runs_before_any_delete():
    """The shared gate is called before any statement executes."""
    gate_at = _CODE.index("_assert_may_delete_labour")
    assert "DELETE FROM" not in _CODE[:gate_at]


def test_the_flag_is_checked_before_the_role():
    """The flag is what makes shipping these endpoints safe at all, so it is
    the first thing evaluated."""
    assert _GATE.index("allow_labour_delete") < _GATE.index("_LABOUR_DELETE_ROLES")


def test_privileged_roles_may_delete_and_others_may_not():
    """A bare == "ADMIN" locked out OWNER and SUPER_ADMIN, which are already
    admin-equivalent for privileged actions elsewhere in the codebase -- and
    those are exactly the accounts clearing test data."""
    roles = workforce_router._LABOUR_DELETE_ROLES
    assert {"ADMIN", "OWNER", "SUPER_ADMIN"} <= roles
    for denied in ("SITE_ENGINEER", "PROJECT_MANAGER", "FINANCE", "", "USER"):
        assert denied not in roles, denied


def test_both_gates_are_present_not_just_one():
    """Either alone is insufficient: the role check would make this live in
    production, and the flag alone would let any logged-in user use it."""
    assert "allow_labour_delete" in _GATE
    assert "_LABOUR_DELETE_ROLES" in _GATE


def test_the_disabled_message_names_the_flag():
    """A bare 403 sends someone reading logs on a hunt."""
    assert "MESIRI_ALLOW_LABOUR_DELETE" in _GATE


# --- Blast radius ----------------------------------------------------------

def test_workers_are_never_deleted():
    """Attendance references the register. A worker outliving their attendance
    is correct; the reverse orphans every line pointing at them."""
    assert "workforce_workers" not in _CODE


def test_only_this_report_is_touched():
    """Every statement is keyed on the one report id -- no unqualified DELETE
    that could clear a table."""
    for stmt in ("labour_attendance_attachments", "labour_attendance_lines"):
        idx = _CODE.index(stmt)
        tail = _CODE[idx : idx + 200]
        assert "report_id = :id" in tail, stmt
    assert "labour_attendance_reports WHERE id = :id" in _CODE


def test_the_self_reference_is_cleared_before_the_report_row_goes():
    """corrects_report_id has no cascade, so deleting a superseded report while
    its replacement still points at it fails with an FK violation."""
    unlink = _CODE.index("SET corrects_report_id = NULL")
    delete_report = _CODE.index("DELETE FROM labour_attendance_reports")
    assert unlink < delete_report


def test_the_outbox_row_is_cleaned_up():
    """No foreign key there, so nothing would complain about a row pointing at
    a report that no longer exists."""
    assert "outbox_events" in _CODE
    assert "aggregate_id = :id" in _CODE


def test_the_organization_is_checked_from_the_row_not_trusted_from_the_caller():
    """One tenant must never be able to delete another's report."""
    assert "organization_id = :org" in _CODE


def test_project_and_site_scope_are_enforced():
    assert "_site_filter_denied" in _CODE
    assert "_resolve_project_ids" in _CODE


def test_a_missing_report_is_a_404_not_a_silent_success():
    assert "404" in _CODE


# --- Reporting back --------------------------------------------------------

def test_the_response_says_what_was_removed():
    """A bare 204 hides whether one line went or fifty."""
    fields = workforce_router.DeleteAttendanceReportResponse.model_fields
    for name in (
        "deleted_lines",
        "deleted_attachments",
        "deleted_outbox_events",
        "unlinked_corrections",
        "deleted_workers",
    ):
        assert name in fields, name


def test_deleted_workers_is_always_zero():
    """Stated in the response so the guarantee is visible to the caller, not
    just asserted in a docstring."""
    assert workforce_router.DeleteAttendanceReportResponse.model_fields[
        "deleted_workers"
    ].default == 0


def test_the_refusal_names_the_role_so_it_is_diagnosable():
    """The first version hid the button on a browser-side role guess, so a
    refusal was indistinguishable from a failed deploy. The server says which
    role was rejected."""
    assert "role" in _GATE and "may not delete" in _GATE


def test_the_deletion_is_logged_loudly():
    """Irreversible and off-policy: it should be findable in the logs after the
    fact, with who did it."""
    assert "logger.warning" in _CODE
    assert "attendance_deleted" in _CODE
