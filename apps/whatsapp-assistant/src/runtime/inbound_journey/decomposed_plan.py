"""Wires the decomposer into the live message path
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9, §14).

Called from process_inbound_message right after the canonicalization stage,
only when the primary (single-segment) canonicalization came back
UNRECOGNIZED with semantic_type UNKNOWN -- exactly the trace evidence §9
records: a multi-intent message has no representable single semantic_type,
so "unknown" is extraction's honest answer for it, and today that answer
produces the dead-end generic reply. This is the one place that answer gets
a second chance before falling back to it.

## Project/site resolution (added 2026-07-30)

§14's risk table named a real gap: the single-message path's project-
selection and site-selection gates (runtime/inbound_journey/seeding.py)
never ran for a decomposed segment at all. Closed here, once per
decomposition rather than once per segment -- project/site ambiguity is a
property of the SENDER (which projects/sites they're authorized on), not of
any individual segment, so every segment of one message shares the same
answer. _resolve_project_and_site runs before any segment is canonicalized;
if it can't resolve automatically (more than one project, or the resolved
project has more than one site), the already-decomposed segment texts are
held in PendingDecompositionStore while a picker asks -- mirroring
_run_project_gate/_run_site_gate's own "hold + ask" shape, generalized from
one CanonicalEventV2 to N segment texts.

Deliberately NOT covering the material-unit/stock gates (an ambiguous
catalog name, an over-stock usage report) -- those are genuinely
per-segment, not a whole-decomposition property, and are a narrower slice
of real traffic. Still named, still open, in the design doc's risk table.

Every failure mode here degrades to `None` -- "not applicable, fall through
to today's unrecognized-message reply unchanged" -- never an exception that
could take down an otherwise-working message. A message that reaches this
function has already failed single-intent understanding once; there is
nothing this module could do that makes that outcome worse, and several
things (a bad decomposition, a provider outage) that must not make it worse
either.
"""

from __future__ import annotations

from backend.ports import ActorIdentity
from canonicalization import build_canonical_event
from channel.replies import (
    ReplySpec,
    render_no_projects_reply,
    render_plan_preview_reply,
    render_project_picker,
    render_site_picker,
)
from mesiri_ai.ports.decomposition import DecompositionProvider
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.common.ids import new_id
from planning.decomposition import build_plan_from_segments
from planning.plan_store import PlanStore
from planning.preview import render_plan_preview
from runtime.inbound_journey._shared import _log
from runtime.inbound_journey.pending_decomposition import (
    PendingDecomposition,
    PendingDecompositionStore,
)
from understanding.pipeline import UnderstandingPipeline

#: Decomposition only makes sense where there is text to split.
#: IMAGE/DOCUMENT go through vision first and their "text" is a rendering of
#: extracted fields, not something a sender composed as several sentences --
#: out of scope for V1, same narrowness this whole layer states plainly
#: elsewhere (ENTITY_RESOLUTION_PLAN.md ADR-E3).
_DECOMPOSABLE_MODALITIES = (InputModality.TEXT, InputModality.INTERACTIVE, InputModality.VOICE)

#: Deliberately the SAME prefixes resume.py's single-report project/site
#: gates use (render_project_picker/render_site_picker bake these in). Safe
#: to share: PendingReportStore and PendingDecompositionStore are two
#: different Redis keys, and a user is only ever in one pending state at a
#: time by construction (a message goes down the single-report path or the
#: decomposed path, never both) -- so whichever store actually holds
#: something for a given tap is the one that answers, and the other's
#: resume function safely no-ops (its own pop_pending returns None first).
_PROJECT_ROW_PREFIX = "proj_"
_SITE_ROW_PREFIX = "site_"


async def _resolve_project_and_site(
    *,
    actor: ActorIdentity | None,
    resolved: ResolvedContextV2,
    segments: tuple[str, ...],
    expense_categories: list[str] | None,
    pending_decomposition_store: PendingDecompositionStore | None,
    user_id: str,
) -> ResolvedContextV2 | ReplySpec:
    """Resolve project_id/site_id ONCE for the whole decomposition, or hold
    and ask. Returns the (possibly patched) context to proceed with, or a
    ReplySpec to send instead (a picker, or "you have no projects").

    Mirrors _run_project_gate/_run_site_gate's own single-project/single-site
    auto-resolve and fail-open/fail-closed reasoning, but reads from `actor`
    directly rather than a CanonicalEventV2 -- project/site membership is the
    same for every segment of one message, so there is nothing per-segment
    to read it off here.

    Falls through UNRESOLVED (no gate at all) when `actor` is None or
    `pending_decomposition_store` was never wired -- the same degrade every
    other optional dependency in this layer uses, not a new failure mode.
    """
    if resolved.project_id is None and actor is not None:
        if not actor.projects:
            return ReplySpec(text=render_no_projects_reply())
        if len(actor.projects) == 1:
            p = actor.projects[0]
            resolved = resolved.model_copy(update={"project_id": p.id, "context_project_id": p.id})
        elif pending_decomposition_store is not None:
            await pending_decomposition_store.set_pending(
                user_id=user_id,
                pending=PendingDecomposition(
                    segments=segments,
                    resolved=resolved,
                    expense_categories=tuple(expense_categories) if expense_categories else None,
                ),
            )
            return render_project_picker([(p.id, p.name, p.location) for p in actor.projects])
        # else: no store wired -- fall through unresolved.

    if resolved.project_id is not None and resolved.site_id is None and actor is not None:
        sites = [s for s in actor.sites if s.project_id == resolved.project_id]
        if len(sites) == 1:
            s = sites[0]
            resolved = resolved.model_copy(update={"site_id": s.id, "context_site_id": s.id})
        elif len(sites) > 1 and pending_decomposition_store is not None:
            await pending_decomposition_store.set_pending(
                user_id=user_id,
                pending=PendingDecomposition(
                    segments=segments,
                    resolved=resolved,
                    expense_categories=tuple(expense_categories) if expense_categories else None,
                ),
            )
            return render_site_picker([(s.id, s.name) for s in sites], allow_combined=False)
        # else: zero sites (fail open, nothing to choose from) or no store
        # wired -- fall through with site_id still unresolved either way.

    return resolved


async def _build_and_preview_plan(
    *,
    segments: list[str] | tuple[str, ...],
    resolved: ResolvedContextV2,
    pipeline: UnderstandingPipeline,
    expense_categories: list[str] | None,
    plan_store: PlanStore,
    correlation_id: str,
    source_message_id: str,
) -> ReplySpec | None:
    """Per-segment extract -> canonicalize -> entity-link -> persist
    all-PENDING -> the §8 preview. Shared by the fresh-message path
    (try_start_decomposed_plan) and both project/site picker resumes below,
    so a picker tap runs the exact same segment-building logic a message
    that never needed one does."""
    segment_events: list[CanonicalEventV2] = []
    for segment_text in segments:
        try:
            segment_understanding = await pipeline.understand_text_segment(
                segment_text,
                source_message_id=source_message_id,
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
    actor: ActorIdentity | None = None,
    actor_user_id: str = "",
    pending_decomposition_store: PendingDecompositionStore | None = None,
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

    resolved_or_reply = await _resolve_project_and_site(
        actor=actor,
        resolved=resolved,
        segments=tuple(decomposed.segments),
        expense_categories=expense_categories,
        pending_decomposition_store=pending_decomposition_store,
        user_id=actor_user_id,
    )
    if isinstance(resolved_or_reply, ReplySpec):
        return resolved_or_reply
    resolved = resolved_or_reply

    return await _build_and_preview_plan(
        segments=decomposed.segments,
        resolved=resolved,
        pipeline=pipeline,
        expense_categories=expense_categories,
        plan_store=plan_store,
        correlation_id=correlation_id,
        source_message_id=understanding.source_message_id,
    )


async def resume_pending_decomposition_with_project(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_decomposition_store: PendingDecompositionStore,
    plan_store: PlanStore,
    pipeline: UnderstandingPipeline,
    actor: ActorIdentity | None = None,
) -> ReplySpec | None:
    """A tap on the project picker _resolve_project_and_site sent while
    holding a decomposition. Resolves site next (the project just picked may
    still have more than one site) before finally building the plan."""
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = str(message.metadata.get("interactive_reply_id") or "")
    if not row_id.startswith(_PROJECT_ROW_PREFIX):
        return None

    pending = await pending_decomposition_store.pop_pending(user_id=actor_user_id)
    if pending is None:
        return ReplySpec(text="That selection expired — please resend your request.")

    project_id = row_id.removeprefix(_PROJECT_ROW_PREFIX)
    # Re-checked against the authorized set the picker was built from, the
    # same defence resume_pending_report_with_project applies to its own
    # tap -- an interactive reply id is untrusted client input.
    authorized_ids = {p.id for p in actor.projects} if actor is not None else set()
    if project_id not in authorized_ids:
        return ReplySpec(text="That project isn't available to you — please resend your request.")

    resolved = pending.resolved.model_copy(
        update={"project_id": project_id, "context_project_id": project_id}
    )
    expense_categories = list(pending.expense_categories) if pending.expense_categories else None

    resolved_or_reply = await _resolve_project_and_site(
        actor=actor,
        resolved=resolved,
        segments=pending.segments,
        expense_categories=expense_categories,
        pending_decomposition_store=pending_decomposition_store,
        user_id=actor_user_id,
    )
    if isinstance(resolved_or_reply, ReplySpec):
        return resolved_or_reply
    resolved = resolved_or_reply

    return await _build_and_preview_plan(
        segments=pending.segments,
        resolved=resolved,
        pipeline=pipeline,
        expense_categories=expense_categories,
        plan_store=plan_store,
        correlation_id=resolved.correlation_id,
        source_message_id=resolved.source_message_id,
    )


async def resume_pending_decomposition_with_site(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_decomposition_store: PendingDecompositionStore,
    plan_store: PlanStore,
    pipeline: UnderstandingPipeline,
    actor: ActorIdentity | None = None,
) -> ReplySpec | None:
    """A tap on the site picker _resolve_project_and_site sent once project
    was already settled. Project is fixed by this point, so this only ever
    fills in site_id and moves straight to building the plan."""
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = str(message.metadata.get("interactive_reply_id") or "")
    if not row_id.startswith(_SITE_ROW_PREFIX):
        return None

    pending = await pending_decomposition_store.pop_pending(user_id=actor_user_id)
    if pending is None:
        return ReplySpec(text="That selection expired — please resend your request.")

    site_id = row_id.removeprefix(_SITE_ROW_PREFIX)
    authorized_ids = (
        {s.id for s in actor.sites if s.project_id == pending.resolved.project_id}
        if actor is not None
        else set()
    )
    if site_id not in authorized_ids:
        return ReplySpec(text="That site isn't available to you — please resend your request.")

    resolved = pending.resolved.model_copy(update={"site_id": site_id, "context_site_id": site_id})
    expense_categories = list(pending.expense_categories) if pending.expense_categories else None

    return await _build_and_preview_plan(
        segments=pending.segments,
        resolved=resolved,
        pipeline=pipeline,
        expense_categories=expense_categories,
        plan_store=plan_store,
        correlation_id=resolved.correlation_id,
        source_message_id=resolved.source_message_id,
    )
