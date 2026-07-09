"""InteractionHandler — unit tests (fakes only, no LangGraph, no DB)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from interactions.classifier_port import InteractionClassifierPort
from interactions.handler import InteractionHandler
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.interaction_spec import (
    FieldCorrection,
    InteractionIntent,
    InteractionSegment,
    InteractionSpecV2,
)
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows import WorkflowRegistry, WorkflowResumeStatus, WorkflowRunStatus, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
WF = "11111111-1111-4111-8111-1111111111aa"


def _message(text: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.1",
        correlation_id="cor_reply_1",
        sender=SenderInfo(wa_id="919000000000", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text=text,
    )


def _awaiting_state() -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id=WF,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return WorkflowStateV2(
        workflow_instance_id=WF,
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="c1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=draft,
        pending_prompt="Confirm?",
    )


class FakeGraph:
    async def ainvoke(self, state: dict) -> dict:
        self.last_state = state
        draft = _awaiting_state().draft_action
        draft.fields = state.get("collected_fields", {})
        return {
            "draft_action": draft,
            "pending_prompt": "Updated prompt",
        }


class FakeInteractionClassifier(InteractionClassifierPort):
    def __init__(self):
        self.next_response: InteractionSpecV2 | None = None
        self.calls = []

    async def classify(
        self,
        original_text: str,
        translated_text: str | None,
        draft_fields: dict[str, Any],
        correlation_id: str,
    ) -> InteractionSpecV2:
        self.calls.append((original_text, translated_text, draft_fields, correlation_id))
        if self.next_response:
            return self.next_response
        return InteractionSpecV2(version="v2", correlation_id=correlation_id, segments=[])


def _handler(
    repo: FakeWorkflowInstanceRepository, classifier: InteractionClassifierPort | None = None
) -> InteractionHandler:
    registry = WorkflowRegistry()
    registry._compiled[WorkflowKey.MATERIAL_RECEIPT] = FakeGraph()
    return InteractionHandler(WorkflowRuntime(registry=registry, repo=repo), classifier=classifier)


async def test_no_active_workflow_returns_none():
    handler = _handler(FakeWorkflowInstanceRepository())
    assert await handler.handle_fast_path(USR, _message("yes")) is None


async def test_confirm_reply_resumes_and_returns_reply():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    handled = await handler.handle_fast_path(USR, _message("yes"))

    assert handled is not None
    assert handled.result.status is WorkflowResumeStatus.CONFIRMED
    assert "Recorded" in handled.reply_text
    assert repo._rows[WF][0].phase is WorkflowPhase.CONFIRMED


async def test_unrelated_reply_falls_through_to_normal_journey():
    """A user with a pending confirmation can still send an unrelated message —
    it must NOT be swallowed by the active workflow."""
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    handled = await handler.handle_fast_path(USR, _message("50 bags steel arrived at site B"))

    assert handled is None  # → caller runs the normal pipeline
    assert repo._rows[WF][0].phase is WorkflowPhase.AWAITING_CONFIRMATION  # untouched


async def test_duplicate_confirm_is_idempotent():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    handler = _handler(repo)

    first = await handler.handle_fast_path(USR, _message("yes"))
    assert first.result.status is WorkflowResumeStatus.CONFIRMED

    # The workflow is no longer awaiting → a second "yes" finds nothing to resume.
    second = await handler.handle_fast_path(USR, _message("yes"))
    assert second is None
    assert repo._rows[WF][1] == 1  # exactly one transition applied


async def test_slow_path_correction_resumes_with_new_draft():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)

    classifier = FakeInteractionClassifier()
    spec = InteractionSpecV2(
        correlation_id="c1",
        segments=[
            InteractionSegment(
                intent=InteractionIntent.CORRECTION,
                segment_text="make it 60",
                corrections=[FieldCorrection(field_name="quantity", new_value=60)],
            )
        ],
    )
    classifier.next_response = spec

    handler = _handler(repo, classifier=classifier)

    handled = await handler.handle_slow_path(USR, _message("make it 60"), "make it 60", None)

    assert handled is not None
    assert handled.result.status is WorkflowRunStatus.STARTED
    assert handled.reply_text == "Updated prompt"

    # Check that it updated the state in the repo but stayed AWAITING_CONFIRMATION
    updated_state = repo._rows[WF][0]
    assert updated_state.phase is WorkflowPhase.AWAITING_CONFIRMATION
    assert updated_state.collected_fields["quantity"] == 60
    assert updated_state.draft_action.fields["quantity"] == 60


async def test_slow_path_unrelated_falls_through():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)

    classifier = FakeInteractionClassifier()
    spec = InteractionSpecV2(
        correlation_id="c1",
        segments=[InteractionSegment(intent=InteractionIntent.UNRELATED, segment_text="unrelated")],
    )
    classifier.next_response = spec

    handler = _handler(repo, classifier=classifier)

    handled = await handler.handle_slow_path(USR, _message("unrelated"), "unrelated", None)

    assert handled is None
    assert repo._rows[WF][0].phase is WorkflowPhase.AWAITING_CONFIRMATION


async def test_slow_path_concurrent_corrections_rejected():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)

    classifier = FakeInteractionClassifier()
    spec = InteractionSpecV2(
        correlation_id="c1",
        segments=[
            InteractionSegment(
                intent=InteractionIntent.CORRECTION,
                segment_text="make it 60",
                corrections=[FieldCorrection(field_name="quantity", new_value=60)],
            )
        ],
    )
    classifier.next_response = spec

    handler = _handler(repo, classifier=classifier)

    # Instead of modifying the repo before calling the handler, we'll
    # override the transition method to simulate it failing due to OCC.
    async def failing_transition(*args, **kwargs):
        return False

    repo.transition = failing_transition

    handled = await handler.handle_slow_path(USR, _message("make it 60"), "make it 60", None)

    assert handled is not None
    assert handled.result.status is WorkflowRunStatus.FAILED
    assert handled.reply_text == "Sorry, I couldn't apply that update — please try again."


async def test_slow_path_sibling_segments():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)

    classifier = FakeInteractionClassifier()
    # A single message produces TWO segments: a CORRECTION and an UNRELATED
    spec = InteractionSpecV2(
        correlation_id="c1",
        segments=[
            InteractionSegment(
                intent=InteractionIntent.CORRECTION,
                segment_text="make it 60",
                corrections=[FieldCorrection(field_name="quantity", new_value=60)],
            ),
            InteractionSegment(
                intent=InteractionIntent.UNRELATED, segment_text="also 5 workers arrived"
            ),
        ],
    )
    classifier.next_response = spec

    handler = _handler(repo, classifier=classifier)

    handled = await handler.handle_slow_path(
        USR,
        _message("make it 60, also 5 workers arrived"),
        "make it 60, also 5 workers arrived",
        None,
    )

    assert handled is not None
    # 1. The CORRECTION updated the pending workflow
    assert handled.result.status is WorkflowRunStatus.STARTED
    # 2. The UNRELATED segment was collected and returned
    assert handled.unrelated_text == "also 5 workers arrived"

    # Verify the workflow was actually updated
    updated_state = repo._rows[WF][0]
    assert updated_state.draft_action.fields["quantity"] == 60
