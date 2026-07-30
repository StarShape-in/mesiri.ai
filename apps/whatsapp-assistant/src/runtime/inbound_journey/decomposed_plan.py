"""Wires the decomposer into the live message path
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9).

Called from process_inbound_message right after the canonicalization stage,
only when the primary (single-segment) canonicalization came back
UNRECOGNIZED with semantic_type UNKNOWN -- exactly the trace evidence §9
records: a multi-intent message has no representable single semantic_type,
so "unknown" is extraction's honest answer for it, and today that answer
produces the dead-end generic reply. This is the one place that answer gets
a second chance before falling back to it.

Every failure mode here degrades to `None` -- "not applicable, fall through
to today's unrecognized-message reply unchanged" -- never an exception that
could take down an otherwise-working message. A message that reaches this
function has already failed single-intent understanding once; there is
nothing this module could do that makes that outcome worse, and several
things (a bad decomposition, a provider outage) that must not make it worse
either.
"""

from __future__ import annotations

from canonicalization import build_canonical_event
from channel.replies import ReplySpec, render_plan_preview_reply
from mesiri_ai.ports.decomposition import DecompositionProvider
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.common.ids import new_id
from planning.decomposition import build_plan_from_segments
from planning.plan_store import PlanStore
from planning.preview import render_plan_preview
from runtime.inbound_journey._shared import _log
from understanding.pipeline import UnderstandingPipeline

#: Decomposition only makes sense where there is text to split.
#: IMAGE/DOCUMENT go through vision first and their "text" is a rendering of
#: extracted fields, not something a sender composed as several sentences --
#: out of scope for V1, same narrowness this whole layer states plainly
#: elsewhere (ENTITY_RESOLUTION_PLAN.md ADR-E3).
_DECOMPOSABLE_MODALITIES = (InputModality.TEXT, InputModality.INTERACTIVE, InputModality.VOICE)


async def try_start_decomposed_plan(
    *,
    message_modality: InputModality,
    understanding: UnderstandingResult,
    resolved: ResolvedContextV2,
    pipeline: UnderstandingPipeline,
    decomposition: DecompositionProvider | None,
    plan_store: PlanStore | None,
    expense_categories: list[str] | None,
    correlation_id: str,
) -> ReplySpec | None:
    """Attempt to turn an UNKNOWN-classified message into a multi-step Plan.

    Persists the plan (every step PENDING -- see planning/preview.py's
    docstring on why an all-PENDING plan is inert to every other advance
    call) and returns the whole-plan preview (§8, P3) with its own Yes/No --
    nothing is started yet. The Yes tap is handled by
    resume_pending_plan_confirmation, which calls
    runtime/plan_executor.py's begin_plan once the user actually confirms.
    No WorkflowRuntime is needed here for exactly that reason: this function
    never starts a workflow, only persists and describes one.

    Returns None for the caller to fall through to today's behaviour
    unchanged. Never raises.
    """
    if decomposition is None or plan_store is None:
        return None
    if message_modality not in _DECOMPOSABLE_MODALITIES:
        return None
    # normalized_text is, for both text and voice, exactly the text the
    # primary extract()/understand_voice() call was given -- the original
    # message for text, the translated transcript for voice (see
    # understanding/pipeline.py's _handle_text/_handle_voice). Decomposition
    # must see the same text extraction already failed to classify as one
    # thing, not some other derived field.
    text = (understanding.normalized_text or "").strip()
    if not text:
        return None

    try:
        decomposed = await decomposition.decompose(text, correlation_id=correlation_id)
    except Exception:  # noqa: BLE001 -- a provider outage here must fall through
        # to the ordinary unrecognized-message reply, not fail the message.
        _log.warning("plan.decompose_failed correlation_id=%s", correlation_id, exc_info=True)
        return None
    if not decomposed.is_multi_intent:
        return None

    segment_events: list[CanonicalEventV2] = []
    for segment_text in decomposed.segments:
        try:
            segment_understanding = await pipeline.understand_text_segment(
                segment_text,
                source_message_id=understanding.source_message_id,
                correlation_id=correlation_id,
                expense_categories=expense_categories,
            )
            segment_events.append(build_canonical_event(segment_understanding, resolved))
        except Exception:  # noqa: BLE001 -- one bad segment must not sink the
            # rest -- build_plan_from_segments already tolerates fewer
            # segments than were decomposed (its own "skipped" reporting is
            # for segments it receives, not ones that never made it this far;
            # a segment that raised here is simply absent from the plan,
            # same net effect as decomposition itself only splitting off
            # what turned out actionable).
            _log.warning(
                "plan.segment_understand_failed correlation_id=%s segment=%r",
                correlation_id,
                segment_text,
                exc_info=True,
            )
            continue

    result = build_plan_from_segments(segment_events, plan_id=new_id("plan"))
    if result.plan is None:
        return None

    try:
        await plan_store.start_plan(plan=result.plan)
        return render_plan_preview_reply(render_plan_preview(result.plan))
    except Exception:  # noqa: BLE001 -- see module docstring: never let a
        # plan-persist failure take down the message.
        _log.exception("plan.persist_failed correlation_id=%s", correlation_id)
        return None
