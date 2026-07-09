"""Post-M3 inbound journey — v2 contracts with canonical UUID scope."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from canonicalization import build_canonical_event, log_canonical_event
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from interactions.response_handler import render_workflow_run_reply
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from planner import Planner, log_planner_decision
from understanding.pipeline import UnderstandingPipeline
from workflows import WorkflowRunResult, WorkflowRunStatus, WorkflowRuntime, log_workflow_run

_log = logging.getLogger("mesiri.inbound_journey")


@dataclass(slots=True)
class JourneyResult:
    understanding: UnderstandingResult
    resolved_context: ResolvedContextV2 | None
    canonical_event: CanonicalEventV2 | None
    planner_decision: PlannerDecisionV2 | None
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
    understanding = await pipeline.understand(message)

    result = await context_resolver.resolve(message, understanding)
    resolved: ResolvedContextV2 | None = None
    canonical_event: CanonicalEventV2 | None = None
    planner_decision: PlannerDecisionV2 | None = None
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

    if workflow_run is not None and workflow_run.status in (
        WorkflowRunStatus.STARTED,
        WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
    ):
        await send_text(
            message.sender.wa_id,
            render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt),
        )
    else:
        await reply_sender(message, understanding)

    return JourneyResult(
        understanding=understanding,
        resolved_context=resolved,
        canonical_event=canonical_event,
        planner_decision=planner_decision,
        workflow_run=workflow_run,
    )
