"""Post-M3 inbound journey: understanding → context → canonicalize → plan → reply."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from canonicalization import build_canonical_event, log_canonical_event
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from mesiri_contracts.assistant.canonical_event import CanonicalEvent
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecision
from mesiri_contracts.assistant.resolved_context import ResolvedContext
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from planner import Planner, log_planner_decision
from understanding.pipeline import UnderstandingPipeline

_log = logging.getLogger("mesiri.inbound_journey")


@dataclass(slots=True)
class JourneyResult:
    """The full set of artifacts produced by one inbound-message journey."""

    understanding: UnderstandingResult
    resolved_context: ResolvedContext | None
    canonical_event: CanonicalEvent | None
    planner_decision: PlannerDecision | None


async def process_inbound_message(
    message: NormalizedMessage,
    *,
    pipeline: UnderstandingPipeline,
    context_resolver: ContextResolver,
    planner: Planner,
    reply_sender: Callable[[NormalizedMessage, UnderstandingResult], Awaitable[None]],
    context_debug: bool = False,
) -> JourneyResult:
    """Run understanding, resolve context, canonicalize, plan, then send the reply.

    Context resolution failures are logged and do not block the reply — the
    reply path does not yet consume ResolvedContext, CanonicalEvent, or
    PlannerDecision (the Workflow Runtime, M6, will be the first real
    consumer). ``resolved_context``, ``canonical_event``, and
    ``planner_decision`` are all ``None`` if context resolution fails —
    canonicalization requires a resolved organization_id/user_id, so it is
    skipped rather than guessed.
    """
    understanding = await pipeline.understand(message)

    result = await context_resolver.resolve(message, understanding)
    resolved: ResolvedContext | None = None
    canonical_event: CanonicalEvent | None = None
    planner_decision: PlannerDecision | None = None
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
    else:
        _log.warning(
            "context.resolution_failed correlation_id=%s error_code=%s",
            message.correlation_id,
            result.error.error_code if result.error else "unknown",
        )

    await reply_sender(message, understanding)
    return JourneyResult(
        understanding=understanding,
        resolved_context=resolved,
        canonical_event=canonical_event,
        planner_decision=planner_decision,
    )
