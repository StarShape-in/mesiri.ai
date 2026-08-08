"""The team-photo offer: when it appears, and what it does with the answer.

Recommended, never required. Attendance is already recorded before this is
sent, so every path through here -- skip, upload, ignore, or a failure --
leaves the record exactly as confirmed.
"""

from __future__ import annotations

import uuid

import pytest

from channel.replies import TEAM_PHOTO_BUTTONS, render_team_photo_offer
from interactions.team_photo_hint import TeamPhotoHintStore
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.inbound_journey import (
    _offer_team_photo,
    _promotion_just_finished,
    _recorded_attendance_report_id,
)
from workflows.runtime import (
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
)

ORG = str(uuid.uuid4())
USR = str(uuid.uuid4())
REPORT = str(uuid.uuid4())


class _FakeRedis:
    """In-memory stand-in with the same set/get contract as the real client."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        self.store[key] = value

    async def get_json(self, key: str):
        return self.store.get(key)


class _Actor:
    organization_id = ORG
    user_id = USR


def _handled(
    *, action=DraftActionType.RECORD_LABOUR_ATTENDANCE, status=ExecutionStatus.SUCCEEDED
):
    from interactions.handler import InteractionHandled

    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id="wf1",
        action_type=action,
        organization_id=ORG,
        user_id=USR,
        fields={"lines": []},
    )
    return InteractionHandled(
        result=WorkflowResumeResult(
            status=WorkflowResumeStatus.CONFIRMED,
            workflow_instance_id="wf1",
            correlation_id="c1",
            confirmed_action=ConfirmedActionV2(
                confirmed_action_id="ca1",
                workflow_instance_id="wf1",
                correlation_id="c1",
                draft_action=draft,
                confirmed_by_user_id=USR,
            ),
        ),
        reply_text="Recorded.",
        execution_result=ExecutionResult(
            status=status,
            idempotency_key="idem1",
            material_row_id=REPORT if status is ExecutionStatus.SUCCEEDED else None,
        ),
    )


# ---------------------------------------------------------------------------
# Which report the photo belongs to
# ---------------------------------------------------------------------------


def test_a_recorded_attendance_yields_its_report_id():
    """material_row_id is the shared "the thing you created" field; for
    labour it carries the attendance report id."""
    assert _recorded_attendance_report_id(_handled()) == REPORT


def test_a_failed_execution_yields_nothing_to_attach_to():
    assert (
        _recorded_attendance_report_id(_handled(status=ExecutionStatus.FAILED)) is None
    )


def test_a_non_attendance_confirmation_yields_nothing():
    """A confirmed expense must never be offered a team photo."""
    assert (
        _recorded_attendance_report_id(
            _handled(action=DraftActionType.RECORD_MATERIAL_RECEIPT)
        )
        is None
    )


# ---------------------------------------------------------------------------
# When the offer follows the promotion step
# ---------------------------------------------------------------------------


def test_the_offer_waits_for_the_promotion_answer():
    """The slot-answer path carries every workflow's answers, so the offer
    has to recognise its own cue rather than firing on any completed
    question."""
    finished = WorkflowRunResult.completed(
        workflow_key=WorkflowKey.WORKER_PROMOTION,
        correlation_id="c1",
        pending_prompt="Added.",
    )
    assert _promotion_just_finished(finished) is True


@pytest.mark.parametrize(
    "result",
    [
        WorkflowRunResult.completed(
            workflow_key=WorkflowKey.EXPENSE_SUBMIT,
            correlation_id="c1",
            pending_prompt="Done.",
        ),
        WorkflowRunResult.awaiting_input(
            workflow_key=WorkflowKey.WORKER_PROMOTION,
            correlation_id="c1",
            workflow_instance_id="wf",
            pending_prompt="Which ones?",
        ),
    ],
)
def test_an_unrelated_or_unfinished_answer_does_not_trigger_the_offer(result):
    """A promotion question still open must not produce the photo offer
    alongside it -- two prompts at once read as one wall of text."""
    assert _promotion_just_finished(result) is False


# ---------------------------------------------------------------------------
# Sending the offer
# ---------------------------------------------------------------------------


async def test_the_offer_parks_the_report_and_sends_the_prompt():
    redis = _FakeRedis()
    store = TeamPhotoHintStore(redis)
    sent: list = []

    async def send(spec, wa_id):
        sent.append((spec, wa_id))

    await _offer_team_photo(REPORT, _Actor(), "wa1", store, send)

    assert await store.pop_hint(user_id=USR) == REPORT
    assert len(sent) == 1
    spec, wa_id = sent[0]
    assert wa_id == "wa1"
    assert spec.buttons == TEAM_PHOTO_BUTTONS


async def test_the_offer_says_the_attendance_is_already_saved():
    """The wording carries the guarantee: a supervisor who ignores this has
    lost nothing, and should be able to see that without asking."""
    text = render_team_photo_offer().text.lower()

    assert "recorded" in text
    assert "skip" in text


async def test_a_failing_hint_store_sends_no_offer():
    """An offer whose answer could never be matched to a report is worse
    than no offer -- the photo would arrive with nowhere to go."""

    class _BrokenRedis(_FakeRedis):
        async def set_json(self, key, value, *, ttl_seconds=None):
            raise RuntimeError("redis down")

    sent: list = []

    async def send(spec, wa_id):
        sent.append(spec)

    await _offer_team_photo(REPORT, _Actor(), "wa1", TeamPhotoHintStore(_BrokenRedis()), send)

    assert sent == []


# ---------------------------------------------------------------------------
# The hint itself
# ---------------------------------------------------------------------------


async def test_the_hint_is_consumed_once():
    """Pop-once matters: without it a photo sent an hour later, meant for
    something else, would silently attach to a closed day's attendance."""
    store = TeamPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, report_id=REPORT)

    assert await store.pop_hint(user_id=USR) == REPORT
    assert await store.pop_hint(user_id=USR) is None


async def test_skipping_clears_the_hint():
    """Scenario 1. After Skip, a photo sent later for some other purpose must
    not be swallowed by an offer already declined."""
    store = TeamPhotoHintStore(_FakeRedis())
    await store.set_hint(user_id=USR, report_id=REPORT)

    await store.clear(user_id=USR)

    assert await store.pop_hint(user_id=USR) is None


async def test_no_hint_is_not_an_error():
    """A user who never got an offer sends photos like anyone else."""
    assert await TeamPhotoHintStore(_FakeRedis()).pop_hint(user_id=USR) is None
