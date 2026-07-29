"""Resume-leg handlers: the resume_pending_report_with_* functions that
continue a report/query held by one of the material/unit/project/site/stock
gates once the user answers the clarifying tap."""

from __future__ import annotations

from backend.ports import ActorIdentity
from channel.replies import (
    ALL_SITES_ROW_ID,
    ReplySpec,
    render_material_create_declined_reply,
    render_material_create_unit_picker,
    render_material_created_reply,
)
from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from planner import Planner
from runtime.inbound_journey._shared import _log
from runtime.inbound_journey.process import _plan_and_run
from runtime.inbound_journey.reply import _complete_resume_leg, _safe
from runtime.inbound_journey.seeding import (
    _run_material_unit_gates,
    _run_project_gate,
    _run_site_gate,
)
from runtime.inventory_query import MaterialInventoryQueryService
from runtime.logging_ports import MessageLogger
from runtime.material_catalog_query import MaterialCatalogQueryService
from workflows import WorkflowRuntime

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
