"""Resume-leg handlers: the resume_pending_report_with_* functions that
continue a report/query held by one of the material/unit/project/site/stock
gates once the user answers the clarifying tap."""

from __future__ import annotations

from backend.ports import ActorIdentity
from channel.replies import (
    ALL_SITES_ROW_ID,
    MEMBER_CANDIDATE_NONE_ROW_ID,
    ReplySpec,
    render_material_create_declined_reply,
    render_material_create_unit_picker,
    render_material_created_reply,
    render_member_create_declined_reply,
    render_member_create_offer,
    render_member_not_found_reply,
)
from interactions.handler import InteractionHandled
from interactions.pending_report import PendingReportStore
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.canonical_event import IntentCompleteness as _IntentCompleteness
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.common.ids import new_id as _new_id
from planner import Planner
from planning.plan import Plan, PlanOrigin, PlanStep, StepRef, StepStatus
from planning.plan_store import PlanStore
from runtime.entity_resolution.member_resolution import MemberNameResolutionService
from runtime.inbound_journey._shared import _log
from runtime.inbound_journey.process import _plan_and_run
from runtime.inbound_journey.reply import _complete_resume_leg, _safe
from runtime.inbound_journey.seeding import (
    _actor_may_create_user,
    _run_material_unit_gates,
    _run_project_gate,
    _run_site_gate,
)
from runtime.inventory_query import MaterialInventoryQueryService
from runtime.logging_ports import MessageLogger
from runtime.material_catalog_query import MaterialCatalogQueryService
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRuntime

_PROJECT_ROW_PREFIX = "proj_"


async def resume_pending_report_with_project(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report that was held by the project-selection gate above, now
    that the user tapped which project it belongs to.

    ``actor_user_id`` is the resolved canonical user_id (the same key the
    gate stored the pending report under) -- not message.sender.wa_id, which
    is the raw phone number the identity gate has already resolved past by
    the time this runs.

    Re-runs the site gate before planner/workflow -- resolving project
    doesn't guarantee site does too (a project can still have more than one
    site to choose between). Returns None for anything that isn't a
    "proj_*" list-row tap, so the caller falls through to the normal journey
    exactly like the other fast-path checks (category tap, greeting,
    whoami).
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_PROJECT_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    project_id = row_id.removeprefix(_PROJECT_ROW_PREFIX)

    # The picker only ever renders actor.projects (see _run_project_gate), but
    # the tapped row_id is untrusted client input -- WhatsApp interactive
    # replies echo back whatever id the button carried, and nothing stops a
    # replayed/crafted payload from naming a project the picker never offered.
    # Re-checking against the same authorized set the picker was built from
    # closes that gap instead of trusting the tap at face value.
    authorized_ids = {p.id for p in actor.projects} if actor is not None else set()
    if project_id not in authorized_ids:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text="That project isn't available to you — please resend your report.")

    event = event.model_copy(update={"project_id": project_id})

    held_reply = await _run_site_gate(
        event,
        actor=actor,
        actor_user_id=actor_user_id,
        pending_report_store=pending_report_store,
        allow_combined=event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED,
    )
    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


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
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report held by the material-resolution gate, now that the user
    tapped which catalog material it refers to.

    Re-runs the remaining gate chain (unit, then project, then site) rather
    than jumping straight to planner -- material resolving doesn't guarantee
    unit/project/site do too (see _run_material_unit_gates: a resolved
    material_id with no unit_id yet still needs the Stock Unit check to
    run). Mirrors resume_pending_report_with_project's shape otherwise.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_MATERIAL_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
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
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    held_reply = await _run_project_gate(
        event, actor=actor, actor_user_id=actor_user_id, pending_report_store=pending_report_store
    )
    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    held_reply = await _run_site_gate(
        event,
        actor=actor,
        actor_user_id=actor_user_id,
        pending_report_store=pending_report_store,
        allow_combined=event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED,
    )
    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


async def resume_pending_report_with_unit(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    catalog_query: MaterialCatalogQueryService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
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
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="No problem — please resend the report with the correct unit.")
    if not row_id.startswith(_UNIT_YES_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    unit_id = row_id.removeprefix(_UNIT_YES_ROW_PREFIX)
    event.fields["unit_id"] = unit_id

    held_reply = await _run_project_gate(
        event, actor=actor, actor_user_id=actor_user_id, pending_report_store=pending_report_store
    )
    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    held_reply = await _run_site_gate(
        event,
        actor=actor,
        actor_user_id=actor_user_id,
        pending_report_store=pending_report_store,
        allow_combined=event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED,
    )
    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        return held_reply

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


_SITE_ROW_PREFIX = "site_"


async def resume_pending_report_with_site(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report/query held by the site-selection gate, now that the
    user tapped which site it belongs to (or "All Sites Combined", for an
    inventory query -- see render_site_picker's allow_combined).

    Site is the last gate in the chain (material/unit/project must already
    be settled to have reached the site gate at all -- see _run_site_gate's
    project_id-is-None short-circuit), so nothing else needs re-running here.
    Returns None for anything that isn't a "site_*" list-row tap, so the
    caller falls through to the normal journey exactly like the other
    fast-path checks.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_SITE_ROW_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    if row_id == ALL_SITES_ROW_ID:
        site_id = None
    else:
        site_id = row_id.removeprefix(_SITE_ROW_PREFIX)
        # Same untrusted-tap concern as the project resume leg above: the
        # picker only ever renders sites from actor.sites for this project
        # (_run_site_gate), so re-check the tap against that same set rather
        # than trusting whatever site_id the interactive reply carried.
        authorized_ids = {s.id for s in actor.sites} if actor is not None else set()
        if site_id not in authorized_ids:
            await _complete_resume_leg(message, event, message_logger)
            return ReplySpec(text="That site isn't available to you — please resend your report.")
    event = event.model_copy(update={"site_id": site_id})

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


_MATERIAL_CREATE_YES_ROW_ID = "matnew_yes"
_MATERIAL_CREATE_NO_ROW_ID = "matnew_no"
_MATERIAL_CREATE_UNIT_PREFIX = "matunit_"


async def _create_material_and_resume(
    event: CanonicalEventV2,
    *,
    unit_id: str,
    unit_display: str,
    message: NormalizedMessage,
    actor_user_id: str,
    catalog_query: MaterialCatalogQueryService,
    pending_report_store: PendingReportStore,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None,
    inventory_query: MaterialInventoryQueryService | None,
    message_logger: MessageLogger | None,
) -> ReplySpec:
    """Create the catalog entry, then run the held report through the rest of
    the gate chain -- shared by both routes into creation (the Yes tap when
    the unit was already known, and the unit-picker tap when it wasn't).

    The created material_id/unit_id are written onto the event before the
    gates re-run, so _run_material_unit_gates takes its already-resolved
    path rather than looking the brand-new name up again.
    """
    name = str(event.fields.get("material_name") or "")
    try:
        created = await catalog_query.create_material(
            organization_id=event.organization_id,
            name=name,
            unit_id=unit_id,
            created_by=actor_user_id,
        )
    except Exception:
        _log.exception("material_create.failed correlation_id=%s", event.correlation_id)
        created = None

    if created is None:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(
            text="Sorry, I couldn't add that material — please try again, or ask your admin."
        )

    event.fields["material_id"] = str(created["id"])
    event.fields["unit_id"] = str(created["default_unit_id"] or unit_id)
    # The reported unit text may have been a synonym of the chosen unit (or
    # absent entirely). Replace it with the canonical display name so the
    # confirmation prompt shows what the material is actually tracked in.
    event.fields["unit"] = unit_display

    confirmation = render_material_created_reply(created["name"], unit_display)

    held_reply = await _run_project_gate(
        event, actor=actor, actor_user_id=actor_user_id, pending_report_store=pending_report_store
    )
    if held_reply is None:
        held_reply = await _run_site_gate(
            event,
            actor=actor,
            actor_user_id=actor_user_id,
            pending_report_store=pending_report_store,
            allow_combined=event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED,
        )

    if held_reply is not None:
        await _complete_resume_leg(message, event, message_logger)
        # Prepend the creation confirmation so the user sees the catalog
        # entry landed even though the report is now paused on a different
        # question (which project/site).
        return ReplySpec(
            text=f"{confirmation}\n\n{held_reply.text}",
            list_button_label=held_reply.list_button_label,
            list_rows=held_reply.list_rows,
            buttons=held_reply.buttons,
        )

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    if reply is None:
        return ReplySpec(text=confirmation)
    return ReplySpec(
        text=f"{confirmation}\n\n{reply.text}",
        list_button_label=reply.list_button_label,
        list_rows=reply.list_rows,
        buttons=reply.buttons,
    )


async def resume_pending_report_with_material_create(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    catalog_query: MaterialCatalogQueryService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report held by the material-create offer, now that the user
    said whether to add the unknown material to the catalog (STA-139).

    On Yes, the Stock Unit is taken from the report's own words when they
    resolved to a real unit ("50 bags of Fevicol" -> bags) so the common case
    costs no extra turn; otherwise a unit picker is sent and creation happens
    on that tap instead (resume_pending_report_with_material_unit_choice).

    On No the report is dropped with a nudge toward a spelling mistake --
    the likeliest reason a real material didn't match -- rather than
    silently closing.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if row_id not in (_MATERIAL_CREATE_YES_ROW_ID, _MATERIAL_CREATE_NO_ROW_ID):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    name = str(event.fields.get("material_name") or "")

    if row_id == _MATERIAL_CREATE_NO_ROW_ID:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text=render_material_create_declined_reply(name))

    # Yes -- try to settle the Stock Unit from what the report already said.
    unit_text = event.fields.get("unit")
    resolved_unit: dict | None = None
    if unit_text:
        try:
            resolved_unit = await catalog_query.resolve_unit(str(unit_text))
        except Exception:
            _log.exception("material_create.unit_lookup_failed correlation_id=%s", event.correlation_id)

    if resolved_unit is not None:
        return await _create_material_and_resume(
            event,
            unit_id=str(resolved_unit["id"]),
            unit_display=resolved_unit.get("display_name") or str(unit_text),
            message=message,
            actor_user_id=actor_user_id,
            catalog_query=catalog_query,
            pending_report_store=pending_report_store,
            planner=planner,
            workflow_runtime=workflow_runtime,
            actor=actor,
            inventory_query=inventory_query,
            message_logger=message_logger,
        )

    # No usable unit in the report -- ask, and create on that tap instead.
    try:
        units = await catalog_query.list_units()
    except Exception:
        _log.exception("material_create.unit_list_failed correlation_id=%s", event.correlation_id)
        units = []
    if not units:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(
            text="Sorry, I couldn't load the units list — please try again, or ask your admin."
        )

    await pending_report_store.set_pending(user_id=actor_user_id, event=event)
    await _complete_resume_leg(message, event, message_logger)
    return render_material_create_unit_picker(
        name, [(str(u["id"]), u["display_name"]) for u in units]
    )


async def resume_pending_report_with_material_unit_choice(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    catalog_query: MaterialCatalogQueryService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report held by the new-material unit picker, now that the
    user chose which unit the material is tracked in. Creates the catalog
    entry and continues the report (STA-139).

    Kept distinct from resume_pending_report_with_unit ("unit_yes_*", the
    Stock Unit *mismatch* clarification for an existing material) -- these
    two answer different questions and must not share a row-id prefix.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not row_id.startswith(_MATERIAL_CREATE_UNIT_PREFIX):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    unit_id = row_id.removeprefix(_MATERIAL_CREATE_UNIT_PREFIX)
    try:
        unit = await catalog_query.get_unit(unit_id)
    except Exception:
        _log.exception("material_create.unit_lookup_failed correlation_id=%s", event.correlation_id)
        unit = None

    return await _create_material_and_resume(
        event,
        unit_id=unit_id,
        unit_display=(unit or {}).get("display_name") or "",
        message=message,
        actor_user_id=actor_user_id,
        catalog_query=catalog_query,
        pending_report_store=pending_report_store,
        planner=planner,
        workflow_runtime=workflow_runtime,
        actor=actor,
        inventory_query=inventory_query,
        message_logger=message_logger,
    )


_STOCK_CAP_ROW_ID = "stock_cap"
_STOCK_ARRIVAL_ROW_ID = "stock_arrival"
_STOCK_CANCEL_ROW_ID = "stock_cancel"


async def resume_pending_report_with_stock_choice(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a usage report held by the stock sufficiency gate
    (_run_stock_gate), now that the user picked how to resolve an over-stock
    report.

    "Cap at available" corrects quantity down to the stock figure the gate
    already computed, then re-runs the same planner/workflow path a normal
    usage report would -- the gate re-checks on the way back through
    _plan_and_run, but requested == available by construction so it never
    re-triggers. "It's an arrival" flips the report to a Material Receipt
    with the same material/quantity/unit -- covers the common mistake of the
    message actually being about stock arriving, not being used. "Cancel"
    discards it, mirroring the wording of a "No" on the normal confirmation
    prompt. Returns None for anything that isn't one of the three "stock_*"
    button taps, so the caller falls through to the normal journey exactly
    like the other fast-path checks.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if row_id not in (_STOCK_CAP_ROW_ID, _STOCK_ARRIVAL_ROW_ID, _STOCK_CANCEL_ROW_ID):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your report.")

    if row_id == _STOCK_CANCEL_ROW_ID:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text="❌ Discarded. Nothing was recorded.")

    if row_id == _STOCK_CAP_ROW_ID:
        event.fields["quantity"] = event.fields.get("available_stock")
    else:  # _STOCK_ARRIVAL_ROW_ID
        event = event.model_copy(
            update={"event_type": CanonicalEventType.MATERIAL_RECEIPT_REQUESTED}
        )
        event.fields["direction"] = "received"
        event.fields.pop("available_stock", None)

    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


# ---------------------------------------------------------------------------
# Member-name resolution resume paths (ENTITY_RESOLUTION_PLAN.md) -- the two
# taps _run_member_name_gate's Ambiguous/Missing outcomes can produce, plus
# the CREATE_USER-then-resume chain Missing's "Yes, create" answer starts.
# ---------------------------------------------------------------------------

_MEMBER_CREATE_YES_ROW_ID = "membernew_yes"
_MEMBER_CREATE_NO_ROW_ID = "membernew_no"

#: Plan step ids for the two-step CREATE_USER -> ADD_PROJECT_MEMBER chain.
#: Constant, not generated, because there is exactly one shape of plan this
#: module ever builds -- see start_member_create_plan below.
_CREATE_USER_STEP_ID = "create_user"
_ADD_MEMBER_STEP_ID = "add_member"


async def resume_pending_report_with_member_candidate(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    member_resolver: MemberNameResolutionService,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    inventory_query: MaterialInventoryQueryService | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report held by the member-name picker (_run_member_name_gate's
    Ambiguous case), now that the sender tapped either a specific candidate
    or "Someone else".

    A specific candidate: re-checks the id is still an active user (it may
    have been deactivated between the offer and the tap) and, if so, patches
    member_name to that user's *current* exact name -- the backend's own
    exact-match resolver (application/projects/name_resolution.py) then
    finds the same row again at execution, so nothing else needs to change
    (ADR-E2). "Someone else": falls through to the same Missing handling
    render_member_create_offer/render_member_not_found_reply would have
    shown, gated by the same role check.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if not row_id or not str(row_id).startswith("member_"):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your request.")

    if row_id == MEMBER_CANDIDATE_NONE_ROW_ID:
        name_hint = str(event.fields.get("member_name") or "")
        actor_role = getattr(actor, "role", None)
        if _actor_may_create_user(actor_role):
            await pending_report_store.set_pending(user_id=actor_user_id, event=event)
            await _complete_resume_leg(message, event, message_logger)
            return render_member_create_offer(name_hint)
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text=render_member_not_found_reply(name_hint))

    entity_id = str(row_id)[len("member_"):]
    try:
        display_name = await member_resolver.get_active_display_name(
            organization_id=event.organization_id, entity_id=entity_id
        )
    except Exception:
        _log.exception("member_candidate.lookup_failed correlation_id=%s", event.correlation_id)
        display_name = None

    if display_name is None:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text="That selection expired — please resend your request.")

    event.fields["member_name"] = display_name
    reply = await _plan_and_run(
        event,
        planner=planner,
        workflow_runtime=workflow_runtime,
        inventory_query=inventory_query,
        pending_report_store=pending_report_store,
        actor_user_id=actor_user_id,
    )
    await _complete_resume_leg(message, event, message_logger)
    return reply


def _resolve_step_field(value: object, outputs_by_step: dict[str, dict[str, str]]) -> object:
    """Resolve a single PlanStep field value if it is a StepRef, otherwise
    return it unchanged. Deliberately narrow -- not the generic recursive
    resolution the composite-request plan layer's Phase 4 will need for
    arbitrary steps, only enough to unblock the one fixed-shape chain this
    module builds (see start_member_create_plan). ADR-C2's just-in-time
    reasoning applies identically at this small scale: the value a StepRef
    names does not exist until the referenced step has actually run."""
    if not isinstance(value, StepRef):
        return value
    return outputs_by_step.get(value.step_id, {}).get(value.output_key)


async def start_member_create_plan(
    *,
    name_hint: str,
    original_event: CanonicalEventV2,
    actor: ActorIdentity | None,
    plan_store: PlanStore,
    workflow_runtime: WorkflowRuntime,
) -> str | None:
    """Start CREATE_USER for real, and remember (in the shared PlanStore)
    that the held ADD_PROJECT_MEMBER request should resume once it succeeds.

    A Plan of exactly two steps -- create_user (RUNNING, started here) and
    add_member (PENDING, its member_name a StepRef pointing at create_user's
    full_name output) -- per ENTITY_RESOLUTION_PLAN.md sections 3.3/8.1: this
    is the entity-resolution layer's continuation, built on the shared
    Plan/PlanStep/PlanStore contracts rather than a standalone mechanism, so
    the composite-request plan layer's Phase 4 has one executor to extend
    rather than a second one to reconcile against.

    add_member's role/created_by_role/project_id travel as literals, copied
    from original_event -- they were already known before the Missing result
    paused this request and never depended on CREATE_USER's outcome. Only
    member_name is a StepRef, because it is the one field CREATE_USER's own
    execution determines (the exact name the new user was actually created
    under).

    Mirrors start_project_setup_followup's "hand-build a PlannerDecisionV2 +
    CanonicalEventV2, then call workflow_runtime.start()" pattern for
    starting CREATE_USER itself -- there is no lower-level shortcut. CREATE_
    USER's role is seeded from the SAME role hint the original add-member
    request carried (a project manager added as PM plausibly gets that as
    their org-wide role too), and CREATE_USER's own build_draft still asks
    for the one field it genuinely cannot infer -- the phone number.

    Returns CREATE_USER's own pending_prompt (its next question, usually the
    phone number), or None if nothing could be started.
    """
    org_id = str(getattr(actor, "organization_id", None) or "")
    user_id = str(getattr(actor, "user_id", None) or "")
    if not org_id or not user_id:
        return None

    role_hint = original_event.fields.get("role")
    corr_id = _new_id("member_create")
    decision = PlannerDecisionV2(
        correlation_id=corr_id,
        source_message_id=corr_id,
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.CREATE_USER,
        reason=CanonicalEventType.CREATE_USER_REQUESTED,
        organization_id=org_id,
        user_id=user_id,
    )
    event = CanonicalEventV2(
        event_id=corr_id,
        correlation_id=corr_id,
        source_message_id=corr_id,
        event_type=CanonicalEventType.CREATE_USER_REQUESTED,
        completeness=_IntentCompleteness.ACTIONABLE,
        organization_id=org_id,
        user_id=user_id,
        fields={
            "full_name": name_hint,
            "role": role_hint,
            "created_by_role": getattr(actor, "role", None),
        },
    )

    await _safe(workflow_runtime.abandon_optional_question(user_id))

    try:
        run = await workflow_runtime.start(decision, event)
    except Exception:  # noqa: BLE001 -- never raise into the tap handler
        _log.exception("member_create_plan.start_failed org=%s", org_id)
        return None
    if not run.pending_prompt:
        _log.error("member_create_plan.no_prompt org=%s status=%s", org_id, run.status.value)
        return None

    # Persisted only AFTER the workflow actually started, so the plan can
    # record the real workflow_instance_id it is waiting on -- the guard that
    # stops an abandoned plan from later attaching itself to a *different*
    # CREATE_USER the same user starts inside the TTL window (see
    # advance_member_plan_after_user_created). Storing first and patching
    # afterwards would leave a window where the plan matches any CREATE_USER;
    # storing after means a failed start simply leaves no plan behind at all,
    # which is also why the two failure branches above no longer need to
    # clear one.
    create_user_step = PlanStep(
        step_id=_CREATE_USER_STEP_ID,
        workflow_key=WorkflowKey.CREATE_USER,
        fields={"full_name": name_hint, "role": role_hint},
        status=StepStatus.RUNNING,
        workflow_instance_id=run.workflow_instance_id,
    )
    add_member_step = PlanStep(
        step_id=_ADD_MEMBER_STEP_ID,
        workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
        fields={
            "member_name": StepRef(step_id=_CREATE_USER_STEP_ID, output_key="full_name"),
            "role": role_hint,
            "created_by_role": original_event.fields.get("created_by_role"),
            "project_id": str(original_event.project_id or ""),
        },
        status=StepStatus.PENDING,
    )
    plan = Plan(
        plan_id=_new_id("plan"),
        correlation_id=original_event.correlation_id,
        user_id=user_id,
        origin=PlanOrigin.RESOLUTION,
        steps=(create_user_step, add_member_step),
    )
    await _safe(plan_store.start_plan(plan=plan))
    return run.pending_prompt


async def resume_pending_report_with_member_create_offer(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    pending_report_store: PendingReportStore,
    plan_store: PlanStore,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None = None,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """Resume a report held by the member-create offer
    (_run_member_name_gate's Missing case), now that the sender said whether
    to create the missing user.

    On Yes, starts the CREATE_USER -> ADD_PROJECT_MEMBER chain (see
    start_member_create_plan) instead of the old dead end. On No, the
    original held event is simply dropped -- there is nothing further to
    resume, mirroring resume_pending_report_with_material_create's decline
    path.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if row_id not in (_MEMBER_CREATE_YES_ROW_ID, _MEMBER_CREATE_NO_ROW_ID):
        return None

    event = await pending_report_store.pop_pending(user_id=actor_user_id)
    if event is None:
        if message_logger:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="That selection expired — please resend your request.")

    name_hint = str(event.fields.get("member_name") or "")

    if row_id == _MEMBER_CREATE_NO_ROW_ID:
        await _complete_resume_leg(message, event, message_logger)
        return ReplySpec(text=render_member_create_declined_reply(name_hint))

    prompt = await start_member_create_plan(
        name_hint=name_hint,
        original_event=event,
        actor=actor,
        plan_store=plan_store,
        workflow_runtime=workflow_runtime,
    )
    await _complete_resume_leg(message, event, message_logger)
    if prompt is None:
        return ReplySpec(
            text="Sorry, I couldn't start that — please try again, or ask your admin."
        )
    return ReplySpec(text=prompt)


async def advance_member_plan_after_user_created(
    handled: InteractionHandled,
    *,
    plan_store: PlanStore,
    workflow_runtime: WorkflowRuntime,
    actor: ActorIdentity | None,
) -> str | None:
    """After a confirmed CREATE_USER execution, check whether it was the
    first step of a member-create plan (start_member_create_plan) and, if
    so, finish the job the original "add X as PM" request actually asked
    for -- start ADD_PROJECT_MEMBER with the newly created user's exact name
    already filled in, instead of leaving the user to re-state their
    original request from scratch.

    Called from runtime/message_journey.py's post-confirmation hook,
    alongside _offer_project_setup -- same shape (inspect a just-confirmed
    execution, decide whether a follow-up fires), different trigger and
    different chain.

    Returns the newly started ADD_PROJECT_MEMBER workflow's own confirmation
    prompt to send, or None if this confirmation wasn't part of a plan this
    function tracks (an ordinary CREATE_USER with no chain is the
    overwhelmingly common case and must be a cheap no-op).
    """
    result = handled.result
    if not isinstance(result, WorkflowResumeResult):
        return None

    user_id = str(getattr(actor, "user_id", None) or "")
    if not user_id:
        return None

    # A plan is only ever waiting on ONE specific CREATE_USER instance. Every
    # decision below matches on that instance id, never on workflow_key alone
    # -- a plan outlives its turn (PlanStore's 30-minute TTL) and the same
    # user can abandon this one and legitimately start a different
    # CREATE_USER inside the window. Matching on key+status alone let an
    # abandoned "create Hysam" plan attach itself to a later "create Rajesh"
    # and offer Rajesh project-manager rights on Hysam's project.
    def _is_our_instance(plan_step: PlanStep | None) -> bool:
        return (
            plan_step is not None
            and plan_step.workflow_instance_id is not None
            and plan_step.workflow_instance_id == result.workflow_instance_id
        )

    # A rejected/cancelled CREATE_USER ends the plan it belonged to. Without
    # this the plan would linger for the rest of its TTL with its first step
    # still RUNNING, waiting for a confirmation that is never coming.
    if result.status in (
        WorkflowResumeStatus.REJECTED,
        WorkflowResumeStatus.CANCELLED,
    ):
        plan = await plan_store.get_plan(user_id=user_id)
        if plan is not None and _is_our_instance(plan.step(_CREATE_USER_STEP_ID)):
            await _safe(plan_store.clear(user_id=user_id))
        return None

    if result.status is not WorkflowResumeStatus.CONFIRMED:
        return None
    confirmed = result.confirmed_action
    if confirmed is None or confirmed.draft_action.action_type is not DraftActionType.CREATE_USER:
        return None
    execution = handled.execution_result
    if execution is None or execution.status is not ExecutionStatus.SUCCEEDED:
        return None

    plan = await plan_store.get_plan(user_id=user_id)
    if plan is None:
        return None
    create_step = plan.step(_CREATE_USER_STEP_ID)
    if create_step is None or create_step.status is not StepStatus.RUNNING:
        return None
    if not _is_our_instance(create_step):
        # Someone else's CREATE_USER (or a plan from before this field
        # existed). Left untouched rather than cleared -- this confirmation
        # is not ours to draw conclusions from, and clearing here would let
        # an unrelated workflow silently cancel a legitimately waiting plan.
        return None

    full_name = confirmed.draft_action.fields.get("full_name")
    if not full_name or not execution.material_row_id:
        await _safe(plan_store.clear(user_id=user_id))
        return None

    try:
        plan = await plan_store.mark_step_done(
            user_id=user_id,
            step_id=_CREATE_USER_STEP_ID,
            outputs={"user_id": execution.material_row_id, "full_name": str(full_name)},
        )
        next_step = await plan_store.next_runnable_step(user_id=user_id)
    except Exception:  # noqa: BLE001 -- the user was created either way; a plan-advance
        # failure must not look like the create itself failed.
        _log.exception("member_plan.advance_failed user=%s", user_id)
        await _safe(plan_store.clear(user_id=user_id))
        return None

    if next_step is None or next_step.step_id != _ADD_MEMBER_STEP_ID:
        await _safe(plan_store.clear(user_id=user_id))
        return None

    outputs_by_step = {s.step_id: s.outputs for s in plan.steps}
    resolved_fields = {
        key: _resolve_step_field(value, outputs_by_step) for key, value in next_step.fields.items()
    }
    project_id = str(resolved_fields.pop("project_id", "") or "")
    await _safe(plan_store.clear(user_id=user_id))
    if not project_id or not resolved_fields.get("member_name"):
        return None

    org_id = str(getattr(actor, "organization_id", None) or "")
    if not org_id:
        return None

    corr_id = _new_id("member_resume")
    decision = PlannerDecisionV2(
        correlation_id=corr_id,
        source_message_id=corr_id,
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.ADD_PROJECT_MEMBER,
        reason=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        organization_id=org_id,
        user_id=user_id,
        project_id=project_id,
    )
    event = CanonicalEventV2(
        event_id=corr_id,
        correlation_id=corr_id,
        source_message_id=corr_id,
        event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        completeness=_IntentCompleteness.ACTIONABLE,
        organization_id=org_id,
        user_id=user_id,
        project_id=project_id,
        fields=resolved_fields,
    )

    await _safe(workflow_runtime.abandon_optional_question(user_id))
    try:
        run = await workflow_runtime.start(decision, event)
    except Exception:  # noqa: BLE001 -- the user was still created successfully
        _log.exception("member_plan.resume_start_failed org=%s", org_id)
        return None
    return run.pending_prompt
