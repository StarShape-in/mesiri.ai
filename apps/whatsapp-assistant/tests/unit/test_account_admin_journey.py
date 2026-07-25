"""runtime/account_admin_journey.py — unit tests (fakes only, no LangGraph, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.ports import ActorIdentity
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.account_admin_journey import try_handle_account_admin_command
from workflows import WorkflowRegistry, WorkflowRunStatus, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _message(text: str, modality: InputModality = InputModality.TEXT) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Ravi"),
        timestamp=datetime(2026, 7, 25, 10, 0, tzinfo=UTC),
        modality=modality,
        text=text,
    )


def _actor(role: str = "ADMIN") -> ActorIdentity:
    return ActorIdentity(
        user_id=USR,
        full_name="Ravi",
        role=role,
        organization_id=ORG,
        org_name="Test Org",
        org_active=True,
    )


class _FakeGraph:
    async def ainvoke(self, state: dict) -> dict:
        draft = DraftActionV2(
            draft_id="d1",
            correlation_id=state["correlation_id"],
            workflow_instance_id=state["workflow_instance_id"],
            action_type=DraftActionType.MANAGE_MONEY_ACCOUNT,
            organization_id=state["organization_id"],
            user_id=state["user_id"],
            fields=state.get("collected_fields", {}),
        )
        return {"draft_action": draft, "pending_prompt": "*Confirm this action?*"}


def _runtime() -> WorkflowRuntime:
    registry = WorkflowRegistry()
    registry._compiled[WorkflowKey.ACCOUNT_ADMIN] = _FakeGraph()
    return WorkflowRuntime(registry=registry, repo=FakeWorkflowInstanceRepository())


async def test_unrecognized_text_returns_none():
    result = await try_handle_account_admin_command(_message("spent 250 on fuel"), _actor(), _runtime())
    assert result is None


async def test_voice_modality_is_ignored_even_with_matching_text():
    result = await try_handle_account_admin_command(
        _message("create account Site Cash", modality=InputModality.VOICE), _actor(), _runtime()
    )
    assert result is None


async def test_create_account_by_admin_starts_a_confirmable_workflow():
    result = await try_handle_account_admin_command(
        _message("create account Site Cash"), _actor(role="ADMIN"), _runtime()
    )
    assert result is not None
    assert result.workflow_run is not None
    assert result.workflow_run.status is WorkflowRunStatus.STARTED
    assert "Confirm this action" in result.reply_text


async def test_create_account_by_finance_role_is_allowed():
    result = await try_handle_account_admin_command(
        _message("create account Site Cash"), _actor(role="FINANCE"), _runtime()
    )
    assert result is not None
    assert result.workflow_run is not None
    assert result.workflow_run.status is WorkflowRunStatus.STARTED


async def test_create_account_by_site_engineer_is_denied():
    result = await try_handle_account_admin_command(
        _message("create account Site Cash"), _actor(role="SITE_ENGINEER"), _runtime()
    )
    assert result is not None
    assert result.workflow_run is None
    assert "Only an admin or finance user" in result.reply_text


async def test_no_actor_is_denied_gracefully():
    result = await try_handle_account_admin_command(_message("create account Site Cash"), None, _runtime())
    assert result is not None
    assert result.workflow_run is None
