"""Post-M3 inbound journey — v2 contracts with canonical UUID scope.

Optionally logs the raw inbound message and one trace row per pipeline stage
(MessageLogger / TraceLogger ports). Loggers are best-effort: a logging
failure is swallowed and never breaks the pipeline.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

from backend.ports import ActorIdentity
from canonicalization import build_canonical_event, log_canonical_event
from channel.replies import (
    ListRow,
    ReplySpec,
    render_clarify_reply,
    render_direct_reply,
    render_understanding_failed_reply,
    render_unsupported_reply,
)
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from interactions.handler import InteractionHandler
from interactions.response_handler import render_workflow_run_reply
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
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


def _render_reply(
    workflow_run: WorkflowRunResult | None,
    workflow_resume: WorkflowResumeResult | None,
    decision: PlannerDecisionV2 | None,
    resolved: ResolvedContextV2 | None,
) -> ReplySpec | None:
    """The single place that decides what the user hears back.

    Returns None only when the interaction leg has already replied. Every other
    path must produce something: a message that reaches the assistant and gets
    no answer is indistinguishable from Mesiri being down.

    Only render_direct_reply's UNRECOGNIZED case ever sets list_rows on the
    returned ReplySpec (the greeting/category menu) -- every other branch is
    plain text, wrapped here so callers only ever handle one return shape.
    """
    if workflow_run is not None and workflow_run.status in (
        WorkflowRunStatus.STARTED,
        WorkflowRunStatus.COMPLETED,
        WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
    ):
        return ReplySpec(
            text=render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt)
        )

    if workflow_resume is not None:
        return None  # interactions/handler.py already sent its own reply

    if workflow_run is not None and workflow_run.status is WorkflowRunStatus.NO_GRAPH:
        # Understood, but expense/labour/equipment graphs don't exist yet.
        return ReplySpec(text=render_unsupported_reply())

    if decision is not None:
        if decision.decision_type is PlannerDecisionType.CLARIFY:
            return ReplySpec(text=render_clarify_reply(decision))
        if decision.decision_type is PlannerDecisionType.DIRECT_REPLY:
            # is_first_message detection isn't wired yet (would need a message-
            # history check) -- defaults to the lighter "returning user" copy.
            return render_direct_reply(
                decision, timezone=resolved.timezone if resolved else None
            )

    # Context resolution failed, understanding was UNUSABLE, the workflow run
    # FAILED, or the planner said IGNORE. Never fall through to format_reply():
    # that is a developer diagnostic ("Type: unknown / Confidence: unusable"),
    # not a reply a site worker should ever receive.
    return ReplySpec(text=render_understanding_failed_reply())


async def process_inbound_message(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pipeline: UnderstandingPipeline,
    context_resolver: ContextResolver,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    interaction_handler: InteractionHandler,
    send_text: Callable[[str, str], Awaitable[Any]],
    send_list: Callable[[str, str, str, tuple[ListRow, ...]], Awaitable[Any]] | None = None,
    context_debug: bool = False,
    message_logger: MessageLogger | None = None,
    trace_logger: TraceLogger | None = None,
    actor: ActorIdentity | None = None,
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
        if understanding.transcript:
            await _safe(mlog.update_body_text(correlation_id=correlation_id, body_text=understanding.transcript))
        for execution in understanding.provider_executions:
            await _safe(tlog.log_provider_execution(
                correlation_id=correlation_id,
                stage="understanding",
                provider=execution.provider,
                operation=execution.operation,
                model=execution.model,
                latency_ms=execution.latency_ms,
                succeeded=execution.succeeded,
                error_code=execution.error_code,
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

    # --- Deterministic identity-lookup fast path (voice + defense-in-depth
    # for text) --- Text is normally already caught by interactions/handler.py's
    # pre-pipeline handle_whoami_trigger, before Understanding even runs (zero
    # AI cost). Voice can't be checked that early -- there's no text until
    # Sarvam transcribes and translates it ("njaan aara" -> "who am I" happens
    # in that same call) -- so this is the first point voice can be recognized.
    # Purely informational and never touches WorkflowRuntime, so it's safe to
    # answer even with a confirmation pending; actor is None only when the
    # caller didn't wire one in (e.g. some tests), in which case this simply
    # doesn't fire.
    #
    # "which text field do I check" is exactly what caused a real bug (the
    # duplicate here checked transcript, the original-language text, instead
    # of normalized_text, the translation); reading Understanding's own
    # answer makes that whole bug class structurally impossible, not just
    # fixed for today.
    # Note: WHOAMI_QUESTION fast-path has been removed to allow a full 
    # LangGraph workflow to process identity lookups with AI-generated replies.

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
            await _safe(mlog.log_reply(correlation_id=correlation_id, reply=handled.reply_text))

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
        try:
            canonical_event = build_canonical_event(understanding, resolved)
            
            # Inject the loaded actor profile into the canonical event so the 
            # WHO_AM_I workflow has the data it needs to generate a reply
            # without breaking the rule against workflows querying the database.
            if canonical_event.event_type is CanonicalEventType.IDENTITY_LOOKUP_REQUESTED and actor is not None:
                canonical_event.fields["actor_profile"] = {
                    "full_name": actor.full_name,
                    "role": actor.role,
                    "org_name": actor.org_name,
                    "projects": [asdict(p) for p in actor.projects] if actor.projects else [],
                    "sites": [asdict(s) for s in actor.sites] if actor.sites else [],
                }

            if context_debug:
                log_canonical_event(canonical_event)
            await _safe(tlog.log_stage(
                correlation_id=correlation_id,
                stage="canonicalization",
                stage_payload=canonical_event.model_dump(mode="json"),
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=True,
            ))
        except Exception as exc:
            await _safe(tlog.log_stage(
                correlation_id=correlation_id,
                stage="canonicalization",
                stage_payload=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            ))
            await _safe(mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__))
            raise

        # --- Planner stage ---
        t0 = time.perf_counter()
        try:
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
        except Exception as exc:
            await _safe(tlog.log_stage(
                correlation_id=correlation_id,
                stage="planner",
                stage_payload=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            ))
            await _safe(mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__))
            raise

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
                await _safe(mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__))
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
    # workflow_resume's own reply was already sent and logged earlier, at the
    # slow-path interaction dispatch above -- _render_reply returns None for
    # that case specifically so it isn't sent (or logged) a second time here.
    reply = _render_reply(workflow_run, workflow_resume, planner_decision, resolved)

    if reply is not None:
        if reply.list_rows and send_list is not None:
            await send_list(
                message.sender.wa_id,
                body=reply.text,
                button_label=reply.list_button_label or "Choose one",
                rows=reply.list_rows,
            )
        elif reply.list_rows:
            # No list-sending capability wired (e.g. a caller that only needs
            # plain text) -- degrade gracefully rather than dropping the menu.
            # Production always wires send_list; this is not the primary UX.
            options = "\n".join(f"  • {row.title}" for row in reply.list_rows)
            await send_text(message.sender.wa_id, f"{reply.text}\n{options}")
        else:
            await send_text(message.sender.wa_id, reply.text)
        await _safe(mlog.log_reply(correlation_id=correlation_id, reply=reply.text))

    await _safe(mlog.mark_completed(correlation_id=correlation_id))

    return JourneyResult(
        understanding=understanding,
        resolved_context=resolved,
        canonical_event=canonical_event,
        planner_decision=planner_decision,
        workflow_run=workflow_run,
        workflow_resume=workflow_resume,
    )
