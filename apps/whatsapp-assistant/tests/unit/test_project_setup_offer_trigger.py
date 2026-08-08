"""Chained project/site setup offer -- unit tests.

Covers _project_setup_offer_target (which offer, if any, follows a confirmed
CREATE_PROJECT/CREATE_SITE), _offer_project_setup (parks it and sends the
button prompt), and start_project_setup_followup (starts SITE_CREATE/
ADD_PROJECT_MEMBER directly once the offer is tapped).

Mirrors test_worker_promotion_trigger.py's fake-runtime style so these stay
fast, isolated unit tests -- no LangGraph, no DB.
"""

from __future__ import annotations

import uuid

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.inbound_journey import (
    _offer_project_setup,
    _project_setup_offer_target,
    start_project_setup_followup,
)
from workflows.runtime import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult

ORG = str(uuid.uuid4())
USR = str(uuid.uuid4())
PRJ = str(uuid.uuid4())
NEW_PROJECT_ID = str(uuid.uuid4())


def _confirmed(
    action_type: DraftActionType, *, project_id: str | None = None, fields: dict | None = None
) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft1",
        correlation_id="cor1",
        workflow_instance_id="wf1",
        action_type=action_type,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        fields=fields or {},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf1",
        workflow_instance_id="wf1",
        correlation_id="cor1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def _handled(confirmed: ConfirmedActionV2, *, material_row_id: str | None, succeeded: bool = True):
    from interactions.handler import InteractionHandled

    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf1",
        correlation_id="cor1",
        confirmed_action=confirmed,
    )
    execution_result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED if succeeded else ExecutionStatus.FAILED,
        idempotency_key="idem1",
        material_row_id=material_row_id,
    )
    return InteractionHandled(result=result, reply_text="ok", execution_result=execution_result)


class _FakeActor:
    def __init__(self, role: str = "ADMIN") -> None:
        self.organization_id = ORG
        self.user_id = USR
        self.role = role


class _FakeOfferStore:
    def __init__(self) -> None:
        self.set_calls: list[dict] = []

    async def set_offer(self, *, user_id: str, stage: str, project_id: str) -> None:
        self.set_calls.append({"user_id": user_id, "stage": stage, "project_id": project_id})


class _BrokenOfferStore:
    async def set_offer(self, **kwargs):
        raise RuntimeError("redis down")


class _FakeWorkflowRuntime:
    def __init__(self, pending_prompt: str | None = "What should the new site be called?") -> None:
        self.started_with: tuple | None = None
        self._pending_prompt = pending_prompt

    async def abandon_optional_question(self, user_id: str) -> bool:
        return False

    async def start(self, decision, event):
        self.started_with = (decision, event)
        if self._pending_prompt is None:
            return WorkflowRunResult.failed(
                workflow_key=decision.workflow_key, correlation_id=event.correlation_id
            )
        return WorkflowRunResult.completed(
            workflow_key=decision.workflow_key,
            correlation_id=event.correlation_id,
            pending_prompt=self._pending_prompt,
        )


# --- _project_setup_offer_target -------------------------------------------


def test_target_after_create_project_is_a_site_offer_with_the_new_id_and_name():
    confirmed = _confirmed(DraftActionType.CREATE_PROJECT, fields={"name": "Skyline Towers"})
    handled = _handled(confirmed, material_row_id=NEW_PROJECT_ID)

    target = _project_setup_offer_target(handled)

    assert target == ("site", NEW_PROJECT_ID, "Skyline Towers")


def test_target_after_create_site_is_a_member_offer_with_the_drafts_own_project_id():
    confirmed = _confirmed(DraftActionType.CREATE_SITE, project_id=PRJ, fields={"name": "Block A"})
    handled = _handled(confirmed, material_row_id="site-row-1")

    target = _project_setup_offer_target(handled)

    assert target == ("member", PRJ, None)


def test_other_action_types_have_no_offer_target():
    confirmed = _confirmed(DraftActionType.RECORD_EXPENSE)
    handled = _handled(confirmed, material_row_id="row1")

    assert _project_setup_offer_target(handled) is None


def test_failed_execution_has_no_offer_target():
    confirmed = _confirmed(DraftActionType.CREATE_PROJECT, fields={"name": "X"})
    handled = _handled(confirmed, material_row_id=None, succeeded=False)

    assert _project_setup_offer_target(handled) is None


# --- _offer_project_setup ----------------------------------------------------


async def test_offer_project_setup_parks_and_sends_the_site_offer():
    confirmed = _confirmed(DraftActionType.CREATE_PROJECT, fields={"name": "Skyline Towers"})
    handled = _handled(confirmed, material_row_id=NEW_PROJECT_ID)
    store = _FakeOfferStore()
    sent: list[tuple] = []

    async def send_reply(spec, wa_id):
        sent.append((spec, wa_id))

    offered = await _offer_project_setup(handled, store, _FakeActor(), "wa123", send_reply)

    assert offered is True
    assert store.set_calls == [{"user_id": USR, "stage": "site", "project_id": NEW_PROJECT_ID}]
    assert len(sent) == 1
    spec, wa_id = sent[0]
    assert wa_id == "wa123"
    assert "Skyline Towers" in spec.text
    assert spec.buttons is not None


async def test_offer_project_setup_no_op_for_an_unrelated_action_type():
    confirmed = _confirmed(DraftActionType.RECORD_EXPENSE)
    handled = _handled(confirmed, material_row_id="row1")
    store = _FakeOfferStore()
    sent: list[tuple] = []

    async def send_reply(spec, wa_id):
        sent.append((spec, wa_id))

    offered = await _offer_project_setup(handled, store, _FakeActor(), "wa123", send_reply)

    assert offered is False
    assert store.set_calls == []
    assert sent == []


async def test_offer_project_setup_store_failure_never_raises():
    confirmed = _confirmed(DraftActionType.CREATE_PROJECT, fields={"name": "X"})
    handled = _handled(confirmed, material_row_id=NEW_PROJECT_ID)
    sent: list[tuple] = []

    async def send_reply(spec, wa_id):
        sent.append((spec, wa_id))

    offered = await _offer_project_setup(
        handled, _BrokenOfferStore(), _FakeActor(), "wa123", send_reply
    )

    assert offered is False
    assert sent == []


# --- start_project_setup_followup -------------------------------------------


async def test_start_site_followup_starts_site_create_with_project_pre_seeded():
    runtime = _FakeWorkflowRuntime(pending_prompt="What should the new site be called?")

    reply = await start_project_setup_followup(
        stage="site", project_id=NEW_PROJECT_ID, actor=_FakeActor(role="ADMIN"), workflow_runtime=runtime
    )

    assert reply is not None and reply.text == "What should the new site be called?"
    decision, event = runtime.started_with
    assert decision.workflow_key is WorkflowKey.SITE_CREATE
    assert decision.project_id == NEW_PROJECT_ID
    assert event.project_id == NEW_PROJECT_ID
    assert event.fields == {"created_by_role": "ADMIN"}


async def test_start_member_followup_starts_add_project_member_with_project_pre_seeded():
    runtime = _FakeWorkflowRuntime(pending_prompt="Who should I add to this project?")

    reply = await start_project_setup_followup(
        stage="member", project_id=PRJ, actor=_FakeActor(role="PROJECT_MANAGER"), workflow_runtime=runtime
    )

    assert reply is not None and reply.text == "Who should I add to this project?"
    decision, event = runtime.started_with
    assert decision.workflow_key is WorkflowKey.ADD_PROJECT_MEMBER
    assert decision.project_id == PRJ
    assert event.fields == {"created_by_role": "PROJECT_MANAGER"}


async def test_start_followup_returns_none_when_the_run_produces_no_prompt():
    runtime = _FakeWorkflowRuntime(pending_prompt=None)

    reply = await start_project_setup_followup(
        stage="site", project_id=NEW_PROJECT_ID, actor=_FakeActor(), workflow_runtime=runtime
    )

    assert reply is None


async def test_start_followup_never_raises_on_a_broken_runtime():
    class _BrokenRuntime:
        async def abandon_optional_question(self, user_id: str) -> bool:
            return False

        async def start(self, decision, event):
            raise RuntimeError("boom")

    reply = await start_project_setup_followup(
        stage="site", project_id=NEW_PROJECT_ID, actor=_FakeActor(), workflow_runtime=_BrokenRuntime()
    )

    assert reply is None
