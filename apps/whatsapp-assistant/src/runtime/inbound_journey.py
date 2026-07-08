"""Post-M3 inbound journey: understanding → context → canonicalize → plan → workflow → reply."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from canonicalization import build_canonical_event, log_canonical_event
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from mesiri_contracts.assistant.canonical_event import CanonicalEvent
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecision, PlannerDecisionType
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from planner import Planner, log_planner_decision
from understanding.pipeline import UnderstandingPipeline
from workflows import WorkflowRunResult, WorkflowRunStatus, WorkflowRuntime, log_workflow_run

_log = logging.getLogger("mesiri.inbound_journey")


@dataclass(slots=True)
class JourneyResult:
    """The full set of artifacts produced by one inbound-message journey."""

    understanding: UnderstandingResult
    resolved_context: ResolvedContext | None
    canonical_event: CanonicalEvent | None
    planner_decision: PlannerDecision | None
    workflow_run: WorkflowRunResult | None


async def process_inbound_message(
    message: NormalizedMessage,
    *,
    pipeline: UnderstandingPipeline,
    context_resolver: ContextResolver,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    reply_sender: Callable[[NormalizedMessage, UnderstandingResult], Awaitable[None]],
    send_text: Callable[[str, str], Awaitable[Any]],
    context_debug: bool = False,
) -> JourneyResult:
    """Run understanding, resolve context, canonicalize, plan, maybe start a workflow, then reply.

    Context resolution failures are logged and do not block the reply.
    ``resolved_context``, ``canonical_event``, ``planner_decision``, and
    ``workflow_run`` are all ``None`` if context resolution fails —
    canonicalization requires a resolved organization_id/user_id, so
    everything downstream of it is skipped rather than guessed.

    When the Planner decides ``START_WORKFLOW`` and the workflow actually
    starts, the reply is the workflow's confirmation prompt — the first time
    context/planner output changes what the user sees. Every other outcome
    (CLARIFY, DIRECT_REPLY, a failed workflow run, or failed context
    resolution) falls back to the existing understanding-summary reply.
    """
    understanding = await pipeline.understand(message)

    result = await context_resolver.resolve(message, understanding)
    resolved: ResolvedContext | None = None
    canonical_event: CanonicalEvent | None = None
    planner_decision: PlannerDecision | None = None
    workflow_run: WorkflowRunResult | None = None

    if result.is_ok:
        resolved = result.unwrap()
        if context_debug:
            log_resolved_context(resolved)
        canonical_event = build_canonical_event(understanding, resolved)
        if context_debug:
            log_canonical_event(canonical_event)
        planner_decision = planner.decide(canonical_event)
        if context_debug:
            log_planner_decision(planner_decision)

        if planner_decision.decision_type is PlannerDecisionType.START_WORKFLOW:
            workflow_run = await workflow_runtime.start(planner_decision, canonical_event)
            if context_debug:
                log_workflow_run(workflow_run)
    else:
        _log.warning(
            "context.resolution_failed correlation_id=%s error_code=%s",
            message.correlation_id,
            result.error.error_code if result.error else "unknown",
        )

    if workflow_run is not None and workflow_run.status is WorkflowRunStatus.STARTED:
        await send_text(message.sender.wa_id, workflow_run.pending_prompt)
    else:
        await reply_sender(message, understanding)

    return JourneyResult(
        understanding=understanding,
        resolved_context=resolved,
        canonical_event=canonical_event,
        planner_decision=planner_decision,
        workflow_run=workflow_run,
    )
