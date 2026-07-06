"""Post-M3 inbound journey: understanding → context → reply."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from context.contract_resolver import ContractContextResolver
from context.runtime import log_resolved_context
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.context.resolved_context import ResolvedContext
from understanding.pipeline import UnderstandingPipeline


async def process_inbound_message(
    message: NormalizedMessage,
    *,
    pipeline: UnderstandingPipeline,
    context_resolver: ContractContextResolver,
    reply_sender: Callable[[NormalizedMessage, UnderstandingResult], Awaitable[None]],
    context_debug: bool = False,
) -> tuple[UnderstandingResult, ResolvedContext]:
    """Run understanding, resolve context, then send the existing WhatsApp reply."""
    understanding = await pipeline.understand(message)
    resolved = await context_resolver.resolve(message, understanding)
    if context_debug:
        log_resolved_context(resolved)
    await reply_sender(message, understanding)
    return understanding, resolved
