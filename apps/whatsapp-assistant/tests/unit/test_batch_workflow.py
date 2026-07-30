"""workflows/batch.py -- segment start, formatting, and outcome summaries
(#1 Multi-Activity, #13 Cross-Module Trigger). Fakes only, no DB/LangGraph.
"""

from __future__ import annotations

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from workflows.batch import (
    format_batch_prefix,
    format_batch_summary,
    format_started_segment_reply,
    render_started_segment_reply_spec,
    start_segment,
    summarize_batch_outcome,
)
from workflows.batch_store import BatchProgress
from workflows.runtime import (
    SlotCandidate,
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
)

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _event() -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields={"narrative": "started painting"},
    )


class _StubPlanner:
    def __init__(self, decision: PlannerDecisionV2) -> None:
        self._decision = decision

    def decide(self, event: CanonicalEventV2) -> PlannerDecisionV2:
        return self._decision


class _StubWorkflowRuntime:
    def __init__(self, result: WorkflowRunResult) -> None:
        self._result = result
        self.calls = 0

    async def start(self, decision, event) -> WorkflowRunResult:
        self.calls += 1
        return self._result


def _start_decision() -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        reason=CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
    )


def _clarify_decision() -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.CLARIFY,
        reason=CanonicalEventType.CLARIFICATION_REQUIRED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        missing_fields=["quantity"],
    )


async def test_start_segment_returns_the_runtime_result_when_planner_starts_a_workflow():
    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    expected = WorkflowRunResult.started(
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        draft_action=draft,
        pending_prompt="Confirm this update?",
    )
    runtime = _StubWorkflowRuntime(expected)
    result = await start_segment(
        _event(), planner=_StubPlanner(_start_decision()), workflow_runtime=runtime
    )
    assert result is expected
    assert runtime.calls == 1


async def test_start_segment_returns_none_when_planner_does_not_start_a_workflow():
    runtime = _StubWorkflowRuntime(
        WorkflowRunResult.failed(workflow_key=WorkflowKey.ACTIVITY_CONTINUATION, correlation_id="cor_1")
    )
    result = await start_segment(
        _event(), planner=_StubPlanner(_clarify_decision()), workflow_runtime=runtime
    )
    assert result is None
    assert runtime.calls == 0  # never even reaches the runtime


def test_format_batch_prefix():
    assert format_batch_prefix(BatchProgress(index=2, total=3, outcomes=())) == "(2 of 3) "


def test_format_started_segment_reply_prefixes_the_prompt_on_started():
    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_2",
        correlation_id="cor_1",
        workflow_instance_id="wf_2",
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    started = WorkflowRunResult.started(
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        correlation_id="cor_1",
        workflow_instance_id="wf_2",
        draft_action=draft,
        pending_prompt="Confirm this update?",
    )
    reply = format_started_segment_reply(started, BatchProgress(index=2, total=3, outcomes=()))
    assert reply == "(2 of 3) Confirm this update?"


def test_format_started_segment_reply_when_planner_declined():
    reply = format_started_segment_reply(None, BatchProgress(index=3, total=3, outcomes=()))
    assert "(3 of 3)" in reply
    assert "couldn't understand" in reply.lower()


def test_format_started_segment_reply_asks_the_question_on_awaiting_input():
    awaiting = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        correlation_id="cor_1",
        workflow_instance_id="wf_3",
        pending_prompt="What's their WhatsApp number?",
    )
    reply = format_started_segment_reply(awaiting, BatchProgress(index=1, total=2, outcomes=()))
    # Previously fell through to the generic "couldn't start this part"
    # fallback, discarding the actual question the workflow was asking.
    assert reply == "(1 of 2) What's their WhatsApp number?"


def test_format_started_segment_reply_no_graph():
    result = WorkflowRunResult.no_graph(workflow_key=WorkflowKey.ACTIVITY_CONTINUATION, correlation_id="cor_1")
    reply = format_started_segment_reply(result, BatchProgress(index=2, total=2, outcomes=()))
    assert "(2 of 2)" in reply
    assert "supported" in reply.lower()


def test_summarize_batch_outcome_confirmed_and_succeeded():
    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    confirmed_action = ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )
    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        confirmed_action=confirmed_action,
    )
    execution_result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED, idempotency_key="k1", material_row_id="row_1"
    )
    assert summarize_batch_outcome(result, execution_result) == "Recorded."


def test_summarize_batch_outcome_confirmed_with_conflict_note():
    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    confirmed_action = ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )
    result = WorkflowResumeResult(
        status=WorkflowResumeStatus.CONFIRMED,
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        confirmed_action=confirmed_action,
    )
    execution_result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED,
        idempotency_key="k1",
        material_row_id="row_1",
        conflict_note="Note: already marked Completed.",
    )
    outcome = summarize_batch_outcome(result, execution_result)
    assert outcome == "Recorded. Note: already marked Completed."


def test_summarize_batch_outcome_rejected_and_cancelled():
    rejected = WorkflowResumeResult(
        status=WorkflowResumeStatus.REJECTED, workflow_instance_id="wf_1", correlation_id="cor_1"
    )
    cancelled = WorkflowResumeResult(
        status=WorkflowResumeStatus.CANCELLED, workflow_instance_id="wf_1", correlation_id="cor_1"
    )
    assert summarize_batch_outcome(rejected, None) == "Discarded."
    assert summarize_batch_outcome(cancelled, None) == "Cancelled."


def test_format_batch_summary_lists_every_outcome_in_order():
    summary = format_batch_summary(("1. Recorded.", "2. Discarded.", "3. Not supported yet."))
    assert "1. Recorded." in summary
    assert "2. Discarded." in summary
    assert "3. Not supported yet." in summary
    assert summary.index("1. Recorded.") < summary.index("2. Discarded.") < summary.index(
        "3. Not supported yet."
    )


def test_format_batch_summary_empty_outcomes_is_empty_string():
    assert format_batch_summary(()) == ""


# --- render_started_segment_reply_spec ---------------------------------------
# The bug this closes: the batch continuation used to concatenate
# format_started_segment_reply's plain string onto the JUST-RESOLVED segment's
# reply, so a next segment that started a real confirmable draft (STARTED)
# rendered "Reply YES to confirm or NO to cancel" with no tappable buttons --
# same bug class as the CREATE_USER/account-admin/project-setup fixes.


def test_started_segment_reply_spec_carries_yes_no_buttons():
    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_2",
        correlation_id="cor_1",
        workflow_instance_id="wf_2",
        action_type=DraftActionType.ADD_PROGRESS_UPDATE,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    started = WorkflowRunResult.started(
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        correlation_id="cor_1",
        workflow_instance_id="wf_2",
        draft_action=draft,
        pending_prompt="Confirm this update?",
    )
    spec = render_started_segment_reply_spec(started, BatchProgress(index=2, total=3, outcomes=()))
    assert spec.text == "(2 of 3) Confirm this update?"
    assert spec.buttons is not None
    assert {b.title for b in spec.buttons} == {"Yes", "No"}


def test_started_segment_reply_spec_carries_a_tappable_list_for_slot_options():
    awaiting = WorkflowRunResult.awaiting_input(
        workflow_key=WorkflowKey.ACTIVITY_CONTINUATION,
        correlation_id="cor_1",
        workflow_instance_id="wf_3",
        pending_prompt="Which account?",
        slot_options=(
            SlotCandidate(value="acc_1", label="Site Cash"),
            SlotCandidate(value="acc_2", label="Petty Cash"),
        ),
    )
    spec = render_started_segment_reply_spec(awaiting, BatchProgress(index=1, total=2, outcomes=()))
    assert spec.text == "(1 of 2) Which account?"
    assert spec.list_rows is not None
    assert {row.title for row in spec.list_rows} == {"Site Cash", "Petty Cash"}
    assert spec.buttons is None


def test_started_segment_reply_spec_plain_text_when_planner_declined():
    spec = render_started_segment_reply_spec(None, BatchProgress(index=3, total=3, outcomes=()))
    assert spec.buttons is None
    assert spec.list_rows is None
    assert "couldn't understand" in spec.text.lower()


def test_started_segment_reply_spec_plain_text_on_no_graph():
    result = WorkflowRunResult.no_graph(workflow_key=WorkflowKey.ACTIVITY_CONTINUATION, correlation_id="cor_1")
    spec = render_started_segment_reply_spec(result, BatchProgress(index=2, total=2, outcomes=()))
    assert spec.buttons is None
    assert spec.list_rows is None
    assert "supported" in spec.text.lower()
