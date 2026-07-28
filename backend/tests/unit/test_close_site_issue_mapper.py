"""application/progress/mapper.py::build_close_site_issue_command -- pure
shape-mapping, no I/O. Mirrors test_report_site_issue_mapper.py's pattern.
"""

from __future__ import annotations

import uuid

from mesiri.application.progress.mapper import build_close_site_issue_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

_ORG_ID = str(uuid.uuid4())
_USER_ID = str(uuid.uuid4())
_ISSUE_ID = str(uuid.uuid4())


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CLOSE_SITE_ISSUE,
        organization_id=_ORG_ID,
        user_id=_USER_ID,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=_USER_ID,
    )


def test_maps_a_fully_populated_draft():
    confirmed = _confirmed(
        {"action": "RESOLVE", "site_issue_id": _ISSUE_ID, "resolution_notes": "Pump replaced"}
    )
    cmd = build_close_site_issue_command(confirmed)
    assert cmd.organization_id == _ORG_ID
    assert cmd.site_issue_id == _ISSUE_ID
    assert cmd.action == "resolve"
    assert cmd.resolution_notes == "Pump replaced"
    assert cmd.created_by == _USER_ID
    assert cmd.idempotency_key == "wf_1"


def test_action_is_lowercased():
    cmd = build_close_site_issue_command(
        _confirmed({"action": "Acknowledge", "site_issue_id": _ISSUE_ID})
    )
    assert cmd.action == "acknowledge"


def test_resolution_notes_defaults_to_none():
    cmd = build_close_site_issue_command(_confirmed({"action": "acknowledge", "site_issue_id": _ISSUE_ID}))
    assert cmd.resolution_notes is None
