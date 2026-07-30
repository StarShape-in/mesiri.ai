"""Sequential multi-segment batch orchestration (#1 Multi-Activity, #13 Cross-Module Trigger).

Lives under workflows/ (not interactions/ or runtime/) specifically so it is
importable from BOTH interactions/handler.py and runtime/inbound_journey.py
without a circular import -- the dependency direction is ingress ->
understanding -> context -> planner -> workflows -> interactions, and
runtime/ (wiring) may import everything. interactions/handler.py needs this
module to advance a batch after a segment's confirmation resolves;
runtime/inbound_journey.py needs it to start the FIRST segment and queue the
rest. Neither of those two may import from each other, so the shared logic
has to sit one layer down, in workflows/.

Deliberately minimal: starting a batch segment is planner.decide() +
workflow_runtime.start(), the same two calls every ordinary single-segment
message already goes through -- no material-specific inventory/stock-gate
injection (runtime/inbound_journey.py's _inject_inventory_context/
_run_stock_gate), since the segments this module currently produces
(canonicalization/builder.py's build_canonical_events) are never material
events. A future segment type that needs those gates would need this module
extended, not worked around.
"""

from __future__ import annotations

from channel.replies import CONFIRM_BUTTONS, ListRow, ReplySpec
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from planner import Planner

from .batch_store import BatchProgress
from .runtime import (
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
    WorkflowRunStatus,
    WorkflowRuntime,
)


async def start_segment(
    event: CanonicalEventV2, *, planner: Planner, workflow_runtime: WorkflowRuntime
) -> WorkflowRunResult | None:
    """Start one batch segment's workflow. None when the planner declines to
    start a workflow at all for this segment (CLARIFY/DIRECT_REPLY/IGNORE) --
    a queued segment is expected to already be actionable (it was
    synthesized or extracted as such), so this is a defensive fallback, not
    the common path."""
    decision = planner.decide(event)
    if decision.decision_type is not PlannerDecisionType.START_WORKFLOW:
        return None
    return await workflow_runtime.start(decision, event)


def format_batch_prefix(progress: BatchProgress) -> str:
    """"(2 of 3) " -- prepended to a segment's own prompt so the user knows
    more is coming and where they are in it. Omitted entirely for a
    single-segment message (progress.total == 1 never reaches this
    function -- see runtime/inbound_journey.py, which only queues/prefixes
    when there IS a remainder)."""
    return f"({progress.index} of {progress.total}) "


def format_started_segment_reply(result: WorkflowRunResult | None, progress: BatchProgress) -> str:
    """The message sent when the NEXT queued segment starts -- either its
    own confirmation prompt (prefixed with batch position) or an honest
    "couldn't process this part" line, never silence."""
    if result is None:
        return f"({progress.index} of {progress.total}) I couldn't understand this part well enough to record it."
    if result.status is WorkflowRunStatus.STARTED:
        return format_batch_prefix(progress) + (result.pending_prompt or "")
    if result.status is WorkflowRunStatus.AWAITING_INPUT:
        # A queued segment missing a field (e.g. CREATE_USER's phone number)
        # asks for it, same as an ordinary single-segment message would --
        # this fell through to the generic "couldn't start this part" line
        # below until now, discarding the actual question entirely.
        return format_batch_prefix(progress) + (result.pending_prompt or "")
    if result.status is WorkflowRunStatus.NO_GRAPH:
        return f"({progress.index} of {progress.total}) That part isn't supported yet."
    if result.status is WorkflowRunStatus.COMPLETED:
        # An informational/no-draft segment (e.g. it resolved to a query or
        # a "nothing to do" outcome) -- report it and the batch keeps moving
        # on its own next resolution, since there is nothing here for the
        # user to confirm.
        return format_batch_prefix(progress) + (result.pending_prompt or "Done.")
    # FAILED / BLOCKED_PENDING_CONFIRMATION -- the latter should not occur in
    # practice (informational segments are exempt from the single-active
    # gate, and a queued segment only ever starts after the PRIOR one fully
    # resolved), but both degrade to the same honest line rather than a crash.
    return f"({progress.index} of {progress.total}) Couldn't start this part — please resend it separately."


def render_started_segment_reply_spec(
    result: WorkflowRunResult | None, progress: BatchProgress
) -> ReplySpec:
    """ReplySpec counterpart to format_started_segment_reply -- same text,
    but carries Yes/No buttons (STARTED) or a tappable list (AWAITING_INPUT
    with slot_options) instead of collapsing to plain text.

    Sent as its own follow-up message (see interactions/handler.py's
    InteractionHandled.next_segment_reply), never concatenated into the
    just-resolved segment's reply -- the same "separate message" shape the
    worker-promotion/team-photo/project-setup follow-ups already use.
    Concatenating a confirmable next segment's prompt into one string is
    exactly how it turned into a "Reply YES to confirm or NO to cancel"
    line with no buttons to tap, the same bug class the CREATE_USER/
    account-admin/project-setup fixes closed elsewhere."""
    text = format_started_segment_reply(result, progress)
    if result is not None and result.status is WorkflowRunStatus.STARTED:
        return ReplySpec(text=text, buttons=CONFIRM_BUTTONS)
    if result is not None and result.status is WorkflowRunStatus.AWAITING_INPUT:
        options = result.slot_options
        # Same WhatsApp list constraints as runtime/inbound_journey/reply.py's
        # render_workflow_run_reply_spec -- degrade to plain text (still
        # answerable by typing) rather than send a request Meta would reject.
        if options and 1 < len(options) <= 10 and all(len(o.label) <= 24 for o in options):
            return ReplySpec(
                text=text,
                list_button_label="Choose one",
                list_rows=tuple(ListRow(o.value, o.label) for o in options),
            )
    return ReplySpec(text=text)


def summarize_batch_outcome(
    result: WorkflowResumeResult, execution_result: ExecutionResult | None
) -> str:
    """One plain-language line for a resolved segment's entry in the
    numbered outcomes log (PendingBatchStore.record_outcome does the
    numbering). Mirrors interactions/response_handler.py's render_resume_reply
    /render_execution_reply wording so the batch summary and the live
    single-segment reply never disagree about what happened."""
    if result.status is WorkflowResumeStatus.REJECTED:
        return "Discarded."
    if result.status is WorkflowResumeStatus.CANCELLED:
        return "Cancelled."
    if result.status is WorkflowResumeStatus.ALREADY_RESOLVED:
        return "Already handled."
    if result.status is WorkflowResumeStatus.NOT_RESUMABLE:
        return "Couldn't be resumed."
    # CONFIRMED
    if execution_result is None:
        return "Confirmed."
    if execution_result.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED):
        if execution_result.conflict_note:
            return f"Recorded. {execution_result.conflict_note}"
        return "Recorded."
    if execution_result.status is ExecutionStatus.REJECTED:
        reasons = "; ".join(execution_result.rejection_reasons)
        return f"Couldn't record: {reasons}"
    return "Something went wrong — please resend this part."


def format_batch_summary(outcomes: tuple[str, ...]) -> str:
    """The closing block once the whole batch has resolved -- every segment
    gets exactly one line, in order, success or failure alike (never a
    blanket "all done" that papers over a partial failure)."""
    if not outcomes:
        return ""
    lines = ["", "*Batch summary:*", *outcomes]
    return "\n".join(lines)
