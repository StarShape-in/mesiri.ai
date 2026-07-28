"""domains/progress/validation.py::validate_close_site_issue -- pure
function, no I/O. Mirrors test_report_site_issue_validation.py's pattern.
"""

from __future__ import annotations

import uuid

from mesiri.domains.progress.validation import validate_close_site_issue
from mesiri_contracts.application.commands.progress import CloseSiteIssueCommand

_ORG_ID = str(uuid.uuid4())
_USER_ID = str(uuid.uuid4())
_ISSUE_ID = str(uuid.uuid4())


def _command(**overrides) -> CloseSiteIssueCommand:
    fields = {
        "command_id": "cmd_1",
        "idempotency_key": "wf_1",
        "correlation_id": "cor_1",
        "organization_id": _ORG_ID,
        "site_issue_id": _ISSUE_ID,
        "action": "resolve",
        "created_by": _USER_ID,
    }
    fields.update(overrides)
    return CloseSiteIssueCommand(**fields)


def test_valid_command_has_no_violations():
    assert validate_close_site_issue(_command()) == []


def test_rejects_unknown_action():
    reasons = validate_close_site_issue(_command(action="delete"))
    assert reasons == ["unknown action 'delete'"]


def test_accepts_every_real_action():
    for action in ("acknowledge", "resolve", "wont_fix"):
        assert validate_close_site_issue(_command(action=action)) == []
