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
    CONFIRM_BUTTONS,
    ListRow,
    ReplySpec,
    render_clarify_reply,
    render_direct_reply,
    render_material_not_found_reply,
    render_material_picker,
    render_no_projects_reply,
    render_project_picker,
    render_understanding_failed_reply,
    render_unit_mismatch_reply,
    render_unsupported_reply,
)
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from interactions.category_hint import CategoryHintStore
from interactions.handler import InteractionHandler
from interactions.pending_report import PendingReportStore
from interactions.response_handler import render_workflow_run_reply
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.canonical_event import IntentCompleteness as _IntentCompleteness
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from planner import Planner, log_planner_decision
from runtime.inventory_query import MaterialInventoryQueryService
from runtime.logging_ports import MessageLogger, TraceLogger
from runtime.material_catalog_query import MaterialCatalogQueryService
from runtime.noop_loggers import NoopMessageLogger, NoopTraceLogger
from runtime.reply_dispatch import send_reply_spec
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
    returned ReplySpec (the greeting/category menu). STARTED and
    BLOCKED_PENDING_CONFIRMATION are the only two statuses that are actually
    asking the user to confirm something -- those get Yes/No buttons.
    COMPLETED (who_am_i, inventory_query) is informational, nothing to
    confirm, so it stays plain text. Every other branch is plain text too,
    wrapped here so callers only ever handle one return shape.
    """
    if workflow_run is not None and workflow_run.status in (
        WorkflowRunStatus.STARTED,
        WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
    ):
        return ReplySpec(
            text=render_workflow_run_reply(
                workflow_run, pending_prompt=workflow_run.pending_prompt
            ),
            buttons=CONFIRM_BUTTONS,
        )

    if workflow_run is not None and workflow_run.status is WorkflowRunStatus.COMPLETED:
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
            return render_direct_reply(decision, timezone=resolved.timezone if resolved else None)

    # Context resolution failed, understanding was UNUSABLE, the workflow run
    # FAILED, or the planner said IGNORE. Never fall through to format_reply():
    # that is a developer diagnostic ("Type: unknown / Confidence: unusable"),
    # not a reply a site worker should ever receive.
    return ReplySpec(text=render_understanding_failed_reply())


_MATERIAL_EVENT_TYPES = frozenset(
    {
        CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        CanonicalEventType.MATERIAL_USAGE_REQUESTED,
    }
)


async def _run_material_unit_gates(
    canonical_event: CanonicalEventV2,
    *,
    catalog_query: MaterialCatalogQueryService,
    pending_report_store: PendingReportStore,
    actor_user_id: str,
) -> ReplySpec | None:
    """Resolve material_id/unit_id against materials_catalog/units_of_measure
    before the report can proceed to the project gate or planner.

    Mutates `canonical_event.fields` in place once resolved. Returns a
    ReplySpec (and holds the event in `pending_report_store`) when the report
    must pause for a clarifying tap -- ambiguous or unmatched material, or a
    reported unit that doesn't match the material's Stock Unit. Returns None
    once both resolve (or if there's nothing to resolve, e.g. no material_name
    at all -- canonicalization's own missing-field check already covers that
    case with CLARIFICATION_REQUIRED).

    Never raises: a lookup failure degrades to "let it through unresolved"
    (None) rather than dropping the reply entirely, same principle as the
    project-selection gate below.
    """
    material_id = canonical_event.fields.get("material_id")
    material: dict | None = None

    if material_id is None:
        name = canonical_event.fields.get("material_name")
        if not name:
            return None
        try:
            candidates = await catalog_query.find_materials(
                organization_id=canonical_event.organization_id, name=name
            )
            if not candidates:
                candidates = await catalog_query.list_active_materials(
                    organization_id=canonical_event.organization_id
                )
        except Exception:
            _log.exception(
                "material_gate.lookup_failed correlation_id=%s", canonical_event.correlation_id
            )
            return None

        if len(candidates) == 1:
            material = candidates[0]
            canonical_event.fields["material_id"] = str(material["id"])
        else:
            await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
            if not candidates:
                return ReplySpec(text=render_material_not_found_reply(name))
            return render_material_picker([(str(c["id"]), c["name"]) for c in candidates])
    else:
        try:
            material = await catalog_query.get_material(
                organization_id=canonical_event.organization_id, material_id=material_id
            )
        except Exception:
            _log.exception(
                "material_gate.lookup_failed correlation_id=%s", canonical_event.correlation_id
            )
            return None
        if material is None or not material["is_active"]:
            return ReplySpec(
                text="That material is no longer available — please resend your report."
            )

    stock_unit_id = material.get("default_unit_id")
    if stock_unit_id is None:
        # No Stock Unit configured on this material yet -- nothing to enforce
        # against (pre-migration catalog entries, or a not-yet-fully-set-up
        # material). Let it through rather than blocking every report.
        return None

    unit_id = canonical_event.fields.get("unit_id")
    if unit_id is not None:
        return None  # already resolved (e.g. a resumed "yes" tap)

    unit_text = canonical_event.fields.get("unit")
    if not unit_text:
        # Omitted entirely -- default to the material's Stock Unit and let the
        # normal confirmation prompt surface it as a field the user can still
        # reject via "NO", rather than adding another clarifying turn.
        canonical_event.fields["unit_id"] = str(stock_unit_id)
        return None

    try:
        resolved_unit = await catalog_query.resolve_unit(unit_text)
    except Exception:
        _log.exception("unit_gate.lookup_failed correlation_id=%s", canonical_event.correlation_id)
        return None

    if resolved_unit is not None and str(resolved_unit["id"]) == str(stock_unit_id):
        canonical_event.fields["unit_id"] = str(stock_unit_id)
        return None

    # Either the reported unit text didn't resolve to anything, or it resolved
    # to a real-but-different unit -- both are a Stock Unit mismatch. Ask,
    # scoped to this material's one valid unit only (never a global picker
    # that would let an incompatible unit through).
    try:
        stock_unit = await catalog_query.get_unit(str(stock_unit_id))
    except Exception:
        _log.exception("unit_gate.lookup_failed correlation_id=%s", canonical_event.correlation_id)
        return None
    await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
    return render_unit_mismatch_reply(
        material_name=material["name"],
        unit_id=str(stock_unit_id),
        unit_display=stock_unit["display_name"] if stock_unit else "the correct unit",
    )


async def _run_project_gate(
    canonical_event: CanonicalEventV2,
    *,
    actor: ActorIdentity | None,
    actor_user_id: str,
    pending_report_store: PendingReportStore,
) -> ReplySpec | None:
    """Ask which project a report belongs to, when it's otherwise ACTIONABLE
    but has no project_id -- factored out of process_inbound_message so the
    material/unit resume functions below can re-run this same gate after
    they resolve their own field, instead of assuming project must already
    be fine (see module docstring on gate re-running)."""
    if canonical_event.completeness is not _IntentCompleteness.ACTIONABLE:
        return None
    if canonical_event.project_id is not None:
        return None
    try:
        if actor is not None and actor.projects:
            await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
            return render_project_picker([(p.id, p.name, p.location) for p in actor.projects])
        return ReplySpec(text=render_no_projects_reply())
    except Exception:
        _log.exception(
            "project_selection_gate.failed correlation_id=%s", canonical_event.correlation_id
        )
        return None


async def _plan_and_run(
    event: CanonicalEventV2,
    *,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
) -> ReplySpec | None:
    """Run the planner and, if it starts a workflow, the workflow -- shared by
    the first-pass journey below and every resume_pending_report_with_*
    function, so a resumed report goes through the exact same decision path
    a first-pass ACTIONABLE report would."""
    decision = planner.decide(event)
    workflow_run: WorkflowRunResult | None = None
    if decision.decision_type is PlannerDecisionType.START_WORKFLOW:
        workflow_run = await workflow_runtime.start(decision, event)
    return _render_reply(workflow_run, None, decision, None)


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
    send_button: Callable[[str, str, tuple[ListRow, ...]], Awaitable[Any]] | None = None,
    send_image: Callable[[str, bytes], Awaitable[Any]] | None = None,
    context_debug: bool = False,
    message_logger: MessageLogger | None = None,
    trace_logger: TraceLogger | None = None,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    catalog_query: MaterialCatalogQueryService | None = None,
    semantic_hint: str | None = None,
    pending_report_store: PendingReportStore | None = None,
    category_hint_store: CategoryHintStore | None = None,
) -> JourneyResult:
    mlog: MessageLogger = message_logger or NoopMessageLogger()
    tlog: TraceLogger = trace_logger or NoopTraceLogger()
    correlation_id = message.correlation_id

    # --- Understanding stage ---
    t0 = time.perf_counter()
    try:
        understanding = await pipeline.understand(message, semantic_hint=semantic_hint)
        await _safe(
            tlog.log_stage(
                correlation_id=correlation_id,
                stage="understanding",
                stage_payload=understanding.model_dump(mode="json"),
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=True,
            )
        )
        if understanding.transcript:
            await _safe(
                mlog.update_body_text(
                    correlation_id=correlation_id, body_text=understanding.transcript
                )
            )
        for execution in understanding.provider_executions:
            await _safe(
                tlog.log_provider_execution(
                    correlation_id=correlation_id,
                    stage="understanding",
                    provider=execution.provider,
                    operation=execution.operation,
                    model=execution.model,
                    latency_ms=execution.latency_ms,
                    succeeded=execution.succeeded,
                    error_code=execution.error_code,
                )
            )
    except Exception as exc:
        await _safe(
            tlog.log_stage(
                correlation_id=correlation_id,
                stage="understanding",
                stage_payload=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
        )
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
            actor_user_id, message, original_text, translated_text, actor=actor
        )
        if handled:
            if handled.reply_image is not None and send_image is not None:
                sent = await send_image(
                    message.sender.wa_id, handled.reply_image, caption=handled.reply_text
                )
                if not sent:
                    await send_text(message.sender.wa_id, handled.reply_text)
            else:
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
    held_reply: ReplySpec | None = None

    if result.is_ok:
        resolved = result.unwrap()
        if context_debug:
            log_resolved_context(resolved)
        await _safe(
            tlog.log_stage(
                correlation_id=correlation_id,
                stage="context",
                stage_payload=resolved.model_dump(mode="json"),
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=True,
            )
        )
        if message_logger:
            await _safe(
                message_logger.update_context(
                    correlation_id=correlation_id,
                    organization_id=resolved.organization_id,
                    project_id=resolved.project_id,
                    site_id=resolved.site_id,
                )
            )

        # --- Canonicalization stage ---
        t0 = time.perf_counter()
        try:
            canonical_event = build_canonical_event(understanding, resolved)

            # Inject the loaded actor profile into the canonical event so the
            # WHO_AM_I workflow has the data it needs to generate a reply
            # without breaking the rule against workflows querying the database.
            if (
                canonical_event.event_type is CanonicalEventType.IDENTITY_LOOKUP_REQUESTED
                and actor is not None
            ):
                canonical_event.fields["actor_profile"] = {
                    "full_name": actor.full_name,
                    "role": actor.role,
                    "org_name": actor.org_name,
                    "projects": [asdict(p) for p in actor.projects] if actor.projects else [],
                    "sites": [asdict(s) for s in actor.sites] if actor.sites else [],
                    "query_text": understanding.translated_text or understanding.normalized_text,
                }

            # Same reasoning as actor_profile above, for the inventory-query
            # workflow: it must not touch the database itself, so the read
            # happens here (the wiring layer) and the result is injected as
            # plain, already-scoped data before the graph ever runs.
            if (
                canonical_event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED
                and inventory_query is not None
            ):
                canonical_event.fields["inventory_levels"] = await inventory_query.query(
                    organization_id=canonical_event.organization_id,
                    project_id=canonical_event.project_id,
                    site_id=canonical_event.site_id,
                    material_name=canonical_event.fields.get("material_name"),
                )

            # A usage report's quantity can't be validated against stock until
            # the confirmation prompt itself (the Domain layer only checks
            # quantity > 0, never sufficiency -- see domains/materials/
            # validation.py). Inject a low-stock hint the same way as
            # inventory_levels above so workflows/material/nodes.py can warn
            # "only X in stock" without querying the database itself.
            if (
                canonical_event.event_type is CanonicalEventType.MATERIAL_USAGE_REQUESTED
                and inventory_query is not None
                and canonical_event.fields.get("material_name")
            ):
                levels = await inventory_query.query(
                    organization_id=canonical_event.organization_id,
                    project_id=canonical_event.project_id,
                    site_id=canonical_event.site_id,
                    material_name=canonical_event.fields.get("material_name"),
                )
                if levels:
                    canonical_event.fields["available_stock"] = levels[0]["current_stock"]

            if context_debug:
                log_canonical_event(canonical_event)
            await _safe(
                tlog.log_stage(
                    correlation_id=correlation_id,
                    stage="canonicalization",
                    stage_payload=canonical_event.model_dump(mode="json"),
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    succeeded=True,
                )
            )
        except Exception as exc:
            await _safe(
                tlog.log_stage(
                    correlation_id=correlation_id,
                    stage="canonicalization",
                    stage_payload=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    succeeded=False,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            await _safe(
                mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__)
            )
            raise

        # --- Material/unit resolution gate ---
        # A material report can be otherwise complete (material_name/quantity/
        # unit all present -> ACTIONABLE) but the reported material/unit text
        # is still free text at this point -- resolve it against the catalog/
        # units_of_measure before the project gate or planner ever see it, so
        # an ambiguous ("cement" -> OPC/PPC) or Stock-Unit-mismatched report
        # is caught here, not as a late domain-validation failure after the
        # user already tapped Yes. See _run_material_unit_gates above.
        if (
            canonical_event.completeness is _IntentCompleteness.ACTIONABLE
            and canonical_event.event_type in _MATERIAL_EVENT_TYPES
            and catalog_query is not None
            and pending_report_store is not None
        ):
            held_reply = await _run_material_unit_gates(
                canonical_event,
                catalog_query=catalog_query,
                pending_report_store=pending_report_store,
                actor_user_id=actor_user_id,
            )

        # --- Project-selection gate ---
        # A report can be otherwise complete (material_name/quantity/unit all
        # present -> ACTIONABLE) but still have no project attached -- the
        # sender has access to more than one project and none is active/
        # default (see context/resolver.py's single-project convenience,
        # which only auto-picks when there's exactly one). Recording it
        # anyway would silently attach it to the wrong project, or fail late
        # at domain validation after the user already tapped Yes (the
        # original bug report this fixes). Ask which project instead, and
        # hold the report so the tap can resume it with project_id filled in.
        if held_reply is None and pending_report_store is not None:
            held_reply = await _run_project_gate(
                canonical_event,
                actor=actor,
                actor_user_id=actor_user_id,
                pending_report_store=pending_report_store,
            )

        if held_reply is None:
            # --- Planner stage ---
            t0 = time.perf_counter()
            try:
                planner_decision = planner.decide(canonical_event)
                if context_debug:
                    log_planner_decision(planner_decision)
                await _safe(
                    tlog.log_stage(
                        correlation_id=correlation_id,
                        stage="planner",
                        stage_payload=planner_decision.model_dump(mode="json"),
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                        succeeded=True,
                    )
                )
            except Exception as exc:
                await _safe(
                    tlog.log_stage(
                        correlation_id=correlation_id,
                        stage="planner",
                        stage_payload=None,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                        succeeded=False,
                        error_code=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                await _safe(
                    mlog.mark_failed(correlation_id=correlation_id, error_code=type(exc).__name__)
                )
                raise

            if planner_decision.decision_type is PlannerDecisionType.START_WORKFLOW:
                # --- Workflow stage ---
                t0 = time.perf_counter()
                try:
                    workflow_run = await workflow_runtime.start(planner_decision, canonical_event)
                    if context_debug:
                        log_workflow_run(workflow_run)
                    # Answering an inventory question ("how much cement is left?")
                    # means the next message is very likely a report about that
                    # same material ("40 bags of cement used...") -- bias the
                    # next message's extraction toward material_update the same
                    # way a category-menu tap does, so it doesn't fall through
                    # to the generic greeting/category menu and force a manual
                    # re-selection. Pop-once TTL (category_hint.py) means it
                    # only ever affects the very next message.
                    if (
                        workflow_run.status is WorkflowRunStatus.COMPLETED
                        and canonical_event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED
                        and category_hint_store is not None
                    ):
                        await category_hint_store.set_hint(
                            user_id=actor_user_id, semantic_hint="material_update"
                        )
                    await _safe(
                        tlog.log_stage(
                            correlation_id=correlation_id,
                            stage="workflow",
                            stage_payload={
                                "status": workflow_run.status.value,
                                "workflow_key": workflow_run.workflow_key.value,
                                "workflow_instance_id": workflow_run.workflow_instance_id,
                            },
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                            succeeded=True,
                        )
                    )
                except Exception as exc:
                    await _safe(
                        tlog.log_stage(
                            correlation_id=correlation_id,
                            stage="workflow",
                            stage_payload=None,
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                            succeeded=False,
                            error_code=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    await _safe(
                        mlog.mark_failed(
                            correlation_id=correlation_id, error_code=type(exc).__name__
                        )
                    )
                    raise
    else:
        error_code = result.error.error_code if result.error else "unknown"
        await _safe(
            tlog.log_stage(
                correlation_id=correlation_id,
                stage="context",
                stage_payload=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                succeeded=False,
                error_code=error_code,
            )
        )
        _log.warning(
            "context.resolution_failed correlation_id=%s error_code=%s",
            correlation_id,
            error_code,
        )

    # --- Send reply ---
    # workflow_resume's own reply was already sent and logged earlier, at the
    # slow-path interaction dispatch above -- _render_reply returns None for
    # that case specifically so it isn't sent (or logged) a second time here.
    # held_reply, when set, always wins: the report is being held pending a
    # material/unit/project clarification, so nothing from planner/workflow
    # ran this turn.
    reply = held_reply or _render_reply(workflow_run, workflow_resume, planner_decision, resolved)

    if reply is not None:
        await send_reply_spec(
            reply,
            message.sender.wa_id,
            send_text=send_text,
            send_list=send_list,
            send_button=send_button,
        )
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


_PROJECT_ROW_PREFIX = "proj_"


async def resume_pending_report_with_project(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
) -> ReplySpec | None:
    """Resume a report that was held by the project-selection gate above, now
    that the user tapped which project it belongs to.

    ``actor_user_id`` is the resolved canonical user_id (the same key the
    gate stored the pending report under) -- not message.sender.wa_id, which
    is the raw phone number the identity gate has already resolved past by
    the time this runs.

    Returns None for anything that isn't a "proj_*" list-row tap, so the
    caller falls through to the normal journey exactly like the other
    fast-path checks (category tap, greeting, whoami).
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_PROJECT_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        return ReplySpec(text="That selection expired — please resend your report.")

    project_id = row_id.removeprefix(_PROJECT_ROW_PREFIX)
    event = event.model_copy(update={"project_id": project_id})

    # Project is the last gate in the chain, so nothing else needs re-running
    # here -- straight to planner/workflow.
    return await _plan_and_run(event, planner=planner, workflow_runtime=workflow_runtime)


_MATERIAL_ROW_PREFIX = "mat_"
_UNIT_YES_ROW_PREFIX = "unit_yes_"
_UNIT_NO_ROW_ID = "unit_no"


async def resume_pending_report_with_material(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    catalog_query: MaterialCatalogQueryService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
) -> ReplySpec | None:
    """Resume a report held by the material-resolution gate, now that the user
    tapped which catalog material it refers to.

    Re-runs the remaining gate chain (unit, then project) rather than jumping
    straight to planner -- material resolving doesn't guarantee unit does too
    (see _run_material_unit_gates: a resolved material_id with no unit_id yet
    still needs the Stock Unit check to run). Mirrors
    resume_pending_report_with_project's shape otherwise.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_MATERIAL_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        return ReplySpec(text="That selection expired — please resend your report.")

    material_id = row_id.removeprefix(_MATERIAL_ROW_PREFIX)
    event.fields["material_id"] = material_id

    held_reply = await _run_material_unit_gates(
        event,
        catalog_query=catalog_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    if held_reply is not None:
        return held_reply

    held_reply = await _run_project_gate(
        event, actor=actor, actor_user_id=actor_user_id, pending_report_store=pending_report_store
    )
    if held_reply is not None:
        return held_reply

    return await _plan_and_run(event, planner=planner, workflow_runtime=workflow_runtime)


async def resume_pending_report_with_unit(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    catalog_query: MaterialCatalogQueryService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
) -> ReplySpec | None:
    """Resume a report held by the unit-mismatch clarification, now that the
    user confirmed or declined the material's Stock Unit.

    "No" doesn't silently fall back to anything -- there's only one valid
    unit for this material in V1 (no unit conversion), so declining means the
    report can't be recorded as stated; the user is asked to resend it
    correctly rather than the assistant guessing.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id:
        return None
    if row_id == _UNIT_NO_ROW_ID:
        # Must still pop -- a stale pending report must never resurrect later.
        await pending_report_store.pop_pending(user_id=actor_user_id)
        return ReplySpec(text="No problem — please resend the report with the correct unit.")
    if not row_id.startswith(_UNIT_YES_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        return ReplySpec(text="That selection expired — please resend your report.")

    unit_id = row_id.removeprefix(_UNIT_YES_ROW_PREFIX)
    event.fields["unit_id"] = unit_id

    held_reply = await _run_project_gate(
        event, actor=actor, actor_user_id=actor_user_id, pending_report_store=pending_report_store
    )
    if held_reply is not None:
        return held_reply

    return await _plan_and_run(event, planner=planner, workflow_runtime=workflow_runtime)
