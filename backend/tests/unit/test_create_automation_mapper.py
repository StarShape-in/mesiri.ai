"""build_command — maps a confirmed workflow action into a
CreateAutomationCommand. Shape-mapping only, no validation."""

from __future__ import annotations

from mesiri.application.automations.create_mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PROJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _confirmed(fields: dict, *, project_id: str | None = None, site_id: str | None = None) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_AUTOMATION,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_basic_reminder_fields():
    confirmed = _confirmed(
        {
            "action": "REMINDER",
            "audience": "SELF",
            "message": "please submit your DPR",
            "frequency": "DAILY",
            "time_of_day": "17:00",
            "created_by_role": "SITE_ENGINEER",
        }
    )
    cmd = build_command(confirmed)

    assert cmd.idempotency_key == "wf_1"
    assert cmd.organization_id == ORG
    assert cmd.created_by == USR
    assert cmd.created_by_role == "SITE_ENGINEER"
    assert cmd.action == "REMINDER"
    assert cmd.audience == "SELF"
    assert cmd.message == "please submit your DPR"
    assert cmd.frequency == "DAILY"
    assert cmd.time_of_day == "17:00"
    assert cmd.project_id is None
    assert cmd.site_id is None


def test_maps_project_and_site_scope_from_draft():
    confirmed = _confirmed(
        {"action": "SEND_DPR", "audience": "SELF", "time_of_day": "09:00"},
        project_id=PROJ,
        site_id=SITE,
    )
    cmd = build_command(confirmed)

    assert cmd.project_id == PROJ
    assert cmd.site_id == SITE


def test_maps_audience_names_and_weekly_day_of_week():
    confirmed = _confirmed(
        {
            "action": "REMINDER",
            "audience": "USERS",
            "audience_names": ["Ilan", "Hysam"],
            "message": "submit your report",
            "frequency": "WEEKLY",
            "day_of_week": 0,
            "time_of_day": "15:00",
        }
    )
    cmd = build_command(confirmed)

    assert cmd.audience_names == ["Ilan", "Hysam"]
    assert cmd.audience_user_ids is None
    assert cmd.day_of_week == 0


def test_maps_already_resolved_audience_user_ids():
    confirmed = _confirmed(
        {
            "action": "REMINDER",
            "audience": "USERS",
            "audience_user_ids": [USR],
            "message": "submit your report",
            "time_of_day": "15:00",
        }
    )
    cmd = build_command(confirmed)

    assert cmd.audience_user_ids == [USR]
