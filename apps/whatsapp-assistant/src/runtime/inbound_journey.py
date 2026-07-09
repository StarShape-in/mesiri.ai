"""Post-M3 inbound journey — v2 contracts with canonical UUID scope.

Optionally logs the raw inbound message and one trace row per pipeline stage
(MessageLogger / TraceLogger ports). Loggers are best-effort: a logging
failure is swallowed and never breaks the pipeline.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from canonicalization import build_canonical_event, log_canonical_event
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from interactions.handler import InteractionHandler
from interactions.response_handler import render_workflow_run_reply
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from planner import Planner, log_planner_decision
from runtime.logging_ports import MessageLogger, TraceLogger
from runtime.noop_loggers import NoopMessageLogger, NoopTraceLogger
from understanding.pipeline import UnderstandingPipeline
from workflows import (
    WorkflowResumeResult,
    WorkflowRunResult,
    WorkflowRunStatus,
    WorkflowRuntime,
    log_workflow_run,
)

_log = logging.getLogger("mesiri.inbound_journey")


@dataclass(slots=True)
class JourneyResult:
    understanding: UnderstandingResult
    resolved_context: ResolvedContextV2 | None
    canonical_event: CanonicalEventV2 | None
    planner_decision: PlannerDecisionV2 | None
    workflow_run: WorkflowRunResult | None
    workflow_resume: WorkflowResumeResult | None = None


async def _safe(coro: Awaitable[None]) -> None:
    """Await a logger coroutine, swallowing any exception."""
    try:
        await coro
    except Exception:  # noqa: BLE001
        _log.warning("logger call failed", exc_info=True)


async def process_inbound_message(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pipeline: UnderstandingPipeline,
    context_resolver: ContextResolver,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    interaction_handler: InteractionHandler,
    reply_sender: Callable[[NormalizedMessage, UnderstandingResult], Awaitable[None]],
    send_text: Callable[[str, str], Awaitable[Any]],
    context_debug: bool = False,
    message_logger: MessageLogger | None = None,
    trace_logger: TraceLogger | None = None,
) -> JourneyResult:
    mlog: MessageLogger = message_logger or NoopMessageLogger()
    tlog: TraceLogger = trace_logger or NoopTraceLogger()
    correlation_id = message.correlation_id

    # --- Understanding stage ---
    t0 = time.perf_counter()
    try:
        understanding = await pipeline.understand(message)
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="understanding",
            stage_payload=understanding.model_dump(mode="json"),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=True,
        ))
    except Exception as exc:
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="understanding",
            stage_payload=None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=False,
            error_code=type(exc).__name__,
            error_message=str(exc),
        ))
        await _safe(mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__))
        raise

    # --- Slow-path interaction dispatch (correction / confirm / reject from classifier) ---
    workflow_resume: WorkflowResumeResult | None = None
    workflow_run: WorkflowRunResult | None = None

    original_text = understanding.transcript or understanding.normalized_text
    translated_text = understanding.translated_text
    if original_text:
        handled = await interaction_handler.handle_slow_path(
            actor_user_id, message, original_text, translated_text
        )
        if handled:
            await send_text(message.sender.wa_id, handled.reply_text)

            if isinstance(handled.result, WorkflowRunResult):
                workflow_run = handled.result
            else:
                workflow_resume = handled.result

            if not handled.unrelated_text:
                return JourneyResult(
                    understanding=understanding,
                    resolved_context=None,
                    canonical_event=None,
                    planner_decision=None,
                    workflow_run=workflow_run,
                    workflow_resume=workflow_resume,
                )

            # The message contained both a workflow interaction AND an unrelated new request.
            # We rewrite the understanding output so the context resolver sees only the new intent.
            understanding.normalized_text = handled.unrelated_text
            understanding.transcript = handled.unrelated_text
            understanding.translated_text = handled.unrelated_text

    # --- Context resolution stage ---
    t0 = time.perf_counter()
    result = await context_resolver.resolve(message, understanding)
    resolved: ResolvedContextV2 | None = None
    canonical_event: CanonicalEventV2 | None = None
    planner_decision: PlannerDecisionV2 | None = None

    if result.is_ok:
        resolved = result.unwrap()
        if context_debug:
            log_resolved_context(resolved)
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="context",
            stage_payload=resolved.model_dump(mode="json"),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=True,
        ))

        # --- Canonicalization stage ---
        t0 = time.perf_counter()
        canonical_event = build_canonical_event(understanding, resolved)
        if context_debug:
            log_canonical_event(canonical_event)
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="canonicalization",
            stage_payload=canonical_event.model_dump(mode="json"),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=True,
        ))

        # --- Planner stage ---
        t0 = time.perf_counter()
        planner_decision = planner.decide(canonical_event)
        if context_debug:
            log_planner_decision(planner_decision)
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="planner",
            stage_payload=planner_decision.model_dump(mode="json"),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=True,
        ))

        if planner_decision.decision_type is PlannerDecisionType.START_WORKFLOW:
            # --- Workflow stage ---
            t0 = time.perf_counter()
            try:
                workflow_run = await workflow_runtime.start(planner_decision, canonical_event)
                if context_debug:
                    log_workflow_run(workflow_run)
                await _safe(tlog.log_stage(
                    correlation_id=correlation_id,
                    stage="workflow",
                    stage_payload={
                        "status": workflow_run.status.value,
                        "workflow_key": workflow_run.workflow_key.value,
                        "workflow_instance_id": workflow_run.workflow_instance_id,
                    },
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    succeeded=True,
                ))
            except Exception as exc:
                await _safe(tlog.log_stage(
                    correlation_id=correlation_id,
                    stage="workflow",
                    stage_payload=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    succeeded=False,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                ))
                raise
    else:
        error_code = result.error.error_code if result.error else "unknown"
        await _safe(tlog.log_stage(
            correlation_id=correlation_id,
            stage="context",
            stage_payload=None,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            succeeded=False,
            error_code=error_code,
        ))
        _log.warning(
            "context.resolution_failed correlation_id=%s error_code=%s",
            correlation_id,
            error_code,
        )

    # --- Send reply ---
    if workflow_run is not None and workflow_run.status in (
        WorkflowRunStatus.STARTED,
        WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
    ):
        await send_text(
            message.sender.wa_id,
            render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt),
        )
    else:
        # Only send the default understanding reply if we didn't just resume a workflow
        if not workflow_resume:
            await reply_sender(message, understanding)

    await _safe(mlog.mark_completed(correlation_id=correlation_id))

    return JourneyResult(
        understanding=understanding,
        resolved_context=resolved,
        canonical_event=canonical_event,
        planner_decision=planner_decision,
        workflow_run=workflow_run,
        workflow_resume=workflow_resume,
    )
