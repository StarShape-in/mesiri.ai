"""Post-M3 inbound journey — v2 contracts with canonical UUID scope.

Optionally logs the raw inbound message and one trace row per pipeline stage
(MessageLogger / TraceLogger ports). Loggers are best-effort: a logging
failure is swallowed and never breaks the pipeline.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

from backend.ports import ActorIdentity
from canonicalization import build_canonical_events, log_canonical_event
from canonicalization.occurred_date import today_for
from channel.replies import (
    ALL_SITES_ROW_ID,
    CONFIRM_BUTTONS,
    ListRow,
    ReplySpec,
    render_clarify_reply,
    render_direct_reply,
    render_material_create_declined_reply,
    render_material_create_offer,
    render_material_create_unit_picker,
    render_material_created_reply,
    render_material_not_found_reply,
    render_material_picker,
    render_no_projects_reply,
    render_project_picker,
    render_site_picker,
    render_understanding_failed_reply,
    render_unit_mismatch_reply,
    render_unsupported_reply,
    render_usage_exceeds_stock_reply,
)
from context.resolver import ContextResolver
from context.runtime import log_resolved_context
from interactions.category_hint import CategoryHintStore
from interactions.handler import InteractionHandled, InteractionHandler
from interactions.pending_report import PendingReportStore
from interactions.response_handler import render_workflow_run_reply
from memory.context_loader import ConversationMemoryLoader
from memory.context_pack import ContextPack
from memory.coordinator import ConversationMemoryCoordinator
from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.canonical_event import IntentCompleteness as _IntentCompleteness
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.common.ids import new_id as _new_id
from planner import Planner, log_planner_decision
from planner.ambiguity import AmbiguityAction, caveat_text, decide_ambiguity
from runtime.activity_query import ActivityQueryService
from runtime.activity_search_service import ActivitySearchService
from runtime.duplicate_expense_query import DuplicateExpenseQueryService
from runtime.escalation_query import EscalationCreateService
from runtime.expense_category_query import ExpenseCategoryQueryService
from runtime.expense_query_service import ExpenseQueryService, resolve_date_range
from runtime.inventory_query import MaterialInventoryQueryService
from runtime.labour_query_service import (
    LabourQueryService,
)
from runtime.labour_query_service import (
    resolve_date_range as resolve_labour_date_range,
)
from runtime.logging_ports import MessageLogger, TraceLogger
from runtime.material_catalog_query import MaterialCatalogQueryService
from runtime.money_account_query import MoneyAccountQueryService
from runtime.noop_loggers import NoopMessageLogger, NoopTraceLogger
from runtime.org_settings_query import OrganizationSettingsQueryService
from runtime.petty_cash_query import PettyCashRecipientQueryService
from runtime.reply_dispatch import send_reply_spec
from runtime.reversal_query import ReversalTargetQueryService
from runtime.vendor_query import VendorQueryService
from runtime.workforce_query import WorkforceQueryService
from understanding.pipeline import UnderstandingPipeline
from workflows import (
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
    WorkflowRunStatus,
    WorkflowRuntime,
    log_workflow_run,
)
from workflows.batch import format_batch_prefix
from workflows.batch_store import BatchProgress, PendingBatchStore

_log = logging.getLogger("mesiri.inbound_journey")

# Matches runtime/account_admin_journey.py's _ACCOUNT_ADMIN_ROLES exactly --
# that module gates the deterministic-parser fast path; this gates the
# AI-understood path (SemanticType.ACCOUNT_ADMIN) so a disallowed role is
# refused the same way regardless of which path a message takes. Kept as a
# second literal (not imported) since the two modules are independent entry
# points by design (see account_admin_journey.py's docstring) -- if this
# ever drifts from that one, tests/unit/test_inbound_journey_account_admin_role.py
# and tests/unit/test_account_admin_journey.py both cover the same role set.
_ACCOUNT_ADMIN_ROLES = frozenset({"ADMIN", "FINANCE"})
_ACCOUNT_ADMIN_DENIED_REPLY = "⛔ Only an admin or finance user can manage accounts."


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


async def _complete_resume_leg(
    message: NormalizedMessage,
    event: CanonicalEventV2,
    message_logger: MessageLogger | None,
) -> None:
    if message_logger is not None:
        await _safe(
            message_logger.update_context(
                correlation_id=message.correlation_id,
                project_id=event.project_id,
                site_id=event.site_id,
            )
        )
        # event.correlation_id survives every pop_pending/model_copy in the
        # material/unit/project gate chain unchanged -- it's always the
        # ORIGINAL report's correlation_id, even N gate-taps later. Tagging
        # every leg's own message with it (a plain string, not a workflow_
        # instance_id FK -- no workflow may exist yet) lets the logs viewer
        # resolve the whole picker chain to one interaction once a workflow
        # instance is eventually created from it (see message_logger.py's
        # list_recent/get_message_detail COALESCE join).
        await _safe(
            message_logger.set_interaction_group(
                correlation_id=message.correlation_id, group_id=event.correlation_id
            )
        )
        await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))


def render_workflow_run_reply_spec(workflow_run: WorkflowRunResult) -> ReplySpec:
    """Turn a WorkflowRunResult into the ReplySpec it should be sent as --
    the one place that decides plain-text vs Yes/No buttons vs a tappable
    list, so every caller that can receive a WorkflowRunResult (starting a
    new workflow, or *resuming* one already in progress -- see
    runtime/dependencies.py's handle_slot_answer fast path) renders it the
    same way. Extracted out of `_render_reply` below (2026-07-26): the fast
    path for resuming a pending slot answer used to skip this entirely and
    always send plain text via send_text, so a resumed workflow that landed
    on STARTED (needs Yes/No) or AWAITING_INPUT (needs another list) never
    got its buttons/list -- exactly the "Reply YES to confirm or NO to
    cancel" plain-text bug a user hit right after answering the account
    slot.

    STARTED and BLOCKED_PENDING_CONFIRMATION are the two statuses actually
    asking the user to confirm a draft -- those get Yes/No buttons.
    AWAITING_INPUT (when the node supplied slot_options -- see
    workflows/slots.py's `slot_options`) gets a tappable list, when every
    label fits WhatsApp's limits. COMPLETED (who_am_i, inventory_query) is
    informational, nothing to confirm, so it stays plain text. NO_GRAPH
    means understood but no compiled graph exists yet. Every other status
    (FAILED, IGNORED, ...) falls back to plain rendered text."""
    if workflow_run.status in (
        WorkflowRunStatus.STARTED,
        WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
    ):
        return ReplySpec(
            text=render_workflow_run_reply(
                workflow_run, pending_prompt=workflow_run.pending_prompt
            ),
            buttons=CONFIRM_BUTTONS,
        )

    if workflow_run.status is WorkflowRunStatus.AWAITING_INPUT:
        text = render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt)
        # A tapped row normalizes to NormalizedMessage.text = its title
        # (ingress/normalization.py's _resolve_interactive_reply), matched
        # by match_slot_answer exactly like a typed reply -- so title must
        # equal the candidate's own label, byte for byte. WhatsApp caps a
        # list at 10 rows and a row title at 24 chars; degrade to plain
        # text (still answerable by typing) rather than send a request Meta
        # would reject outright.
        options = workflow_run.slot_options
        if options and 1 < len(options) <= 10 and all(len(o.label) <= 24 for o in options):
            return ReplySpec(
                text=text,
                list_button_label="Choose one",
                list_rows=tuple(ListRow(o.value, o.label) for o in options),
            )
        return ReplySpec(text=text)

    if workflow_run.status is WorkflowRunStatus.COMPLETED:
        return ReplySpec(
            text=render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt)
        )

    if workflow_run.status is WorkflowRunStatus.NO_GRAPH:
        # Understood, but expense/labour/equipment graphs don't exist yet.
        return ReplySpec(text=render_unsupported_reply())

    return ReplySpec(
        text=render_workflow_run_reply(workflow_run, pending_prompt=workflow_run.pending_prompt)
    )


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

    Every workflow_run status is delegated to render_workflow_run_reply_spec
    above; everything else (a fresh decision with no workflow at all) is
    handled here.
    """
    if workflow_run is not None and workflow_run.status is not WorkflowRunStatus.FAILED:
        return render_workflow_run_reply_spec(workflow_run)

    if workflow_resume is not None:
        return None  # interactions/handler.py already sent its own reply

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

# Mirrors domains/organizations/settings.py's constant of the same name --
# duplicated as a literal rather than imported at module scope so this
# module keeps its "backend imports stay inside function bodies" shape (see
# runtime/material_catalog_query.py's deferred imports).
_WHATSAPP_MATERIAL_CREATE_ROLES = "whatsapp_material_create_roles"


async def _may_create_material(
    canonical_event: CanonicalEventV2,
    *,
    actor_role: str | None,
    org_settings_query: OrganizationSettingsQueryService | None,
) -> bool:
    """Whether this sender's role may add a catalog entry from WhatsApp, per
    the org's own whatsapp_material_create_roles setting (STA-139).

    Denies when there's no settings service wired or no role resolved rather
    than falling back to the spec default -- an unknown actor must not get a
    capability the org may not have granted. The service itself already
    degrades to the default on a lookup failure.
    """
    if org_settings_query is None or not actor_role:
        return False
    allowed = await org_settings_query.get(
        organization_id=canonical_event.organization_id,
        key=_WHATSAPP_MATERIAL_CREATE_ROLES,
    )
    from mesiri.domains.organizations.settings import role_allowed

    return role_allowed(actor_role, allowed)


async def _run_material_unit_gates(
    canonical_event: CanonicalEventV2,
    *,
    catalog_query: MaterialCatalogQueryService,
    pending_report_store: PendingReportStore,
    actor_user_id: str,
    actor_role: str | None = None,
    org_settings_query: OrganizationSettingsQueryService | None = None,
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
            matches = await catalog_query.find_materials(
                organization_id=canonical_event.organization_id, name=name
            )
        except Exception:
            _log.exception(
                "material_gate.lookup_failed correlation_id=%s", canonical_event.correlation_id
            )
            return None

        if len(matches) == 1:
            material = matches[0]
            canonical_event.fields["material_id"] = str(material["id"])
        elif len(matches) > 1:
            await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
            return render_material_picker([(str(c["id"]), c["name"]) for c in matches])
        else:
            # The reported name matched nothing. Offering to add it is
            # checked BEFORE the whole-catalog fallback picker below: once
            # the sender is allowed to create, "add Fevicol" is a far better
            # answer than a list of 20 unrelated materials to pick the wrong
            # one from.
            if await _may_create_material(
                canonical_event, actor_role=actor_role, org_settings_query=org_settings_query
            ):
                await pending_report_store.set_pending(
                    user_id=actor_user_id, event=canonical_event
                )
                return render_material_create_offer(str(name))

            # Not allowed to create -- keep the pre-STA-139 behaviour: offer
            # the org's active catalog so there's still something to pick
            # (the reported name may just be phrased differently), and only
            # dead-end when the catalog is genuinely empty.
            try:
                candidates = await catalog_query.list_active_materials(
                    organization_id=canonical_event.organization_id
                )
            except Exception:
                _log.exception(
                    "material_gate.lookup_failed correlation_id=%s",
                    canonical_event.correlation_id,
                )
                return None
            if not candidates:
                return ReplySpec(text=render_material_not_found_reply(str(name)))
            await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
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
        # Must fail CLOSED, not open: project_id is required by domain
        # validation (validation.py's "project is not resolved"), unlike the
        # material/unit gates above where letting an unresolved field through
        # is safe. Silently proceeding here would let the user tap Yes on a
        # confirmation that's guaranteed to fail two steps later instead of
        # failing honestly right now.
        _log.exception(
            "project_selection_gate.failed correlation_id=%s", canonical_event.correlation_id
        )
        return ReplySpec(
            text="Sorry, something went wrong picking your project — please resend your report."
        )


async def _run_site_gate(
    canonical_event: CanonicalEventV2,
    *,
    actor: ActorIdentity | None,
    actor_user_id: str,
    pending_report_store: PendingReportStore,
    allow_combined: bool,
) -> ReplySpec | None:
    """Ask which site a report/query belongs to, once its project is settled
    but site_id still isn't and the project has more than one site.

    Mirrors _run_project_gate's shape: a single site under the resolved
    project auto-resolves (no ask, no picker) the same way a single
    authorized project already does in context/resolver.py; zero sites lets
    the report through site-less rather than blocking on nothing to choose
    from. Unlike project, site_id is not required by domain validation
    (domains/materials/validation.py never checks it) -- so a failure here
    fails OPEN (let it through unresolved), the same safe degrade the
    material/unit gates use, not the fail-closed project gate needs.

    ``allow_combined`` is only ever True for an inventory query -- asking
    "how much cement" can meaningfully span every site, so its picker offers
    an "All Sites Combined" row; a material report being recorded always
    has to land on one real site, so recording never offers that option."""
    if canonical_event.completeness is not _IntentCompleteness.ACTIONABLE:
        return None
    if canonical_event.site_id is not None:
        return None
    if canonical_event.project_id is None:
        return None  # site only makes sense once a project is settled
    if actor is None:
        return None
    try:
        sites = [s for s in actor.sites if s.project_id == canonical_event.project_id]
        if not sites:
            return None
        if len(sites) == 1:
            canonical_event.site_id = sites[0].id
            return None
        await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
        return render_site_picker(
            [(s.id, s.name) for s in sites], allow_combined=allow_combined
        )
    except Exception:
        _log.exception(
            "site_selection_gate.failed correlation_id=%s", canonical_event.correlation_id
        )
        return None


async def _run_stock_gate(
    canonical_event: CanonicalEventV2,
    *,
    pending_report_store: PendingReportStore,
    actor_user_id: str,
) -> ReplySpec | None:
    """Block a usage report whose quantity exceeds what's in stock, instead
    of the old cosmetic-only warning (workflows/material/nodes.py's
    _low_stock_warning showed "Only X in stock" on the confirmation prompt
    but a Yes tap still saved the full over-limit quantity, driving stock
    negative -- the real-world bug this fixes).

    Must run after _inject_inventory_context has populated available_stock
    on the event's fields, and after every other gate (material/unit/
    project/site) has already resolved -- mirrors their "hold + ask" shape,
    offering three explicit choices (cap at available / this was actually an
    arrival / cancel) rather than guessing which one the user meant. Returns
    None when there's nothing to check (not a usage report, not yet
    actionable, or no stock figure available to compare against) or when the
    requested quantity is within stock.
    """
    if canonical_event.event_type is not CanonicalEventType.MATERIAL_USAGE_REQUESTED:
        return None
    if canonical_event.completeness is not _IntentCompleteness.ACTIONABLE:
        return None
    available = canonical_event.fields.get("available_stock")
    if available is None:
        return None
    try:
        requested = float(canonical_event.fields.get("quantity"))
        available = float(available)
    except (TypeError, ValueError):
        return None
    if requested <= available:
        return None

    await pending_report_store.set_pending(user_id=actor_user_id, event=canonical_event)
    return render_usage_exceeds_stock_reply(
        material_name=str(canonical_event.fields.get("material_name") or "this material"),
        unit=str(canonical_event.fields.get("unit") or ""),
        requested=requested,
        available=available,
    )


async def _inject_inventory_context(
    event: CanonicalEventV2, inventory_query: MaterialInventoryQueryService | None
) -> None:
    """Populate inventory_levels (for INVENTORY_QUERY_ASKED) / available_stock
    (for MATERIAL_USAGE_REQUESTED's low-stock warning) on the event's fields.

    Must only run after every material/unit/project/site gate has already
    resolved project_id/site_id -- project_id/site_id can still change up to
    that point, and computing this any earlier would silently answer for
    the wrong scope once the user picked a different project/site than
    whatever was resolved at canonicalization time. Called from both the
    first-pass journey (inline, right before the planner stage) and
    _plan_and_run (used by every resume_pending_report_with_* function),
    since the first pass has its own inline planner/workflow telemetry and
    doesn't route through _plan_and_run."""
    if inventory_query is None:
        return
    if event.event_type is CanonicalEventType.INVENTORY_QUERY_ASKED:
        event.fields["inventory_levels"] = await inventory_query.query(
            organization_id=event.organization_id,
            project_id=event.project_id,
            site_id=event.site_id,
            material_name=event.fields.get("material_name"),
        )
    elif (
        event.event_type is CanonicalEventType.MATERIAL_USAGE_REQUESTED
        and event.fields.get("material_name")
    ):
        # A usage report's quantity can't be validated against stock until
        # the confirmation prompt itself (the Domain layer only checks
        # quantity > 0, never sufficiency -- see domains/materials/
        # validation.py). This hint lets workflows/material/nodes.py warn
        # "only X in stock" without querying the database itself.
        levels = await inventory_query.query(
            organization_id=event.organization_id,
            project_id=event.project_id,
            site_id=event.site_id,
            material_name=event.fields.get("material_name"),
        )
        if levels:
            event.fields["available_stock"] = levels[0]["current_stock"]


async def _seed_account_candidates(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    money_account_query: MoneyAccountQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Feed the org's eligible money accounts into the event's fields so
    expense_capture's resolve_account node (Finance Module Slice 1) and
    transfer's resolve_from_account/resolve_to_account nodes (Slice 3) can
    decide whether to auto-fill, ask "which account?", or proceed unset --
    a node must never query a repository itself (see workflows/runtime.py's
    docstring), so this is the seeding point, same principle as
    _inject_inventory_context above. Only ever runs for EXPENSE_SUBMIT and
    TRANSFER; every other workflow key's fields are left untouched.

    TRANSFER additionally gets `created_by_role` seeded here -- it travels
    through the draft the same way amount/from/to do, so
    application/finance/transfer_validation.py can enforce who may transfer
    money without threading actor identity through the ExecutionDispatcher
    protocol for every domain (see transfer_commands.py's docstring).
    """
    if money_account_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key not in (
        WorkflowKey.EXPENSE_SUBMIT,
        WorkflowKey.TRANSFER,
        WorkflowKey.PETTY_CASH,
    ):
        return
    accounts = await money_account_query.list_accounts(
        organization_id=actor.organization_id, created_by=actor.user_id
    )
    event.fields["account_candidates"] = [
        {"id": str(account.id), "name": account.name} for account in accounts
    ]
    if decision.workflow_key in (WorkflowKey.TRANSFER, WorkflowKey.PETTY_CASH):
        event.fields["created_by_role"] = actor.role


async def _seed_petty_cash_recipient(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    petty_cash_query: PettyCashRecipientQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Resolve `recipient_name` (e.g. "Alan") into their employee-advance
    money account, auto-created on first issuance -- Finance Module Slice 5.
    A node must never query a repository itself, so this is the seeding
    point, same principle as _seed_account_candidates above. Only ever runs
    for PETTY_CASH; an unresolved recipient (no matching active user) simply
    leaves `recipient_account_id` unset -- workflows/petty_cash/nodes.py's
    build_draft then produces a draft missing that leg of the transfer,
    which the existing transfer_validation.py rejects rather than this
    seeding step guessing who was meant."""
    if petty_cash_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.PETTY_CASH:
        return
    recipient_name = event.fields.get("recipient_name")
    if not recipient_name:
        return
    account = await petty_cash_query.resolve_or_create_advance_account(
        organization_id=actor.organization_id,
        recipient_name=str(recipient_name),
        created_by=actor.user_id,
    )
    if account is not None:
        event.fields["recipient_account_id"] = str(account.id)
        event.fields["recipient_account_name"] = account.name


async def _seed_reversal_target(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    reversal_query: ReversalTargetQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Resolve "the most recent expense/transfer" into a concrete id --
    Finance Module Slice 7. A node must never query a repository itself, so
    this is the seeding point, same principle as _seed_account_candidates
    above. Only ever runs for REVERSE; finding nothing simply leaves
    `expense_id`/`money_transaction_id` unset -- workflows/reverse/nodes.py's
    build_draft then completes with a "nothing to reverse" reply instead of
    a draft (see that module's docstring and
    `WorkflowDefinition.allows_completion_without_draft` in
    workflows/registry.py).

    #6 Undo: a bare "undo"/"delete that" (mesiri_ai.undo_classifier) produces
    a REVERSAL event with no target_kind at all -- canonicalization/
    mapping.py defaults that specific case (target_kind absent, not merely
    unrecognized) to CanonicalEventType.EXPENSE_REVERSAL_REQUESTED purely so
    routing has a type to dispatch on; the REAL kind is resolved here, by
    reversal_query.find_latest_of_either_kind, and written back onto
    target_kind so workflows/reverse/nodes.py's confirmation prompt and
    "nothing to reverse" message render for whichever kind actually won."""
    if reversal_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.REVERSE:
        return
    event.fields["created_by_role"] = actor.role
    target_kind = str(event.fields.get("target_kind", "")).strip().lower()

    if not target_kind:
        found = await reversal_query.find_latest_of_either_kind(
            organization_id=actor.organization_id,
            project_id=event.project_id,
            site_id=event.site_id,
        )
        if found is None:
            # Deliberately leave target_kind unset (not "expense" or
            # "transfer") -- workflows/reverse/nodes.py's build_draft falls
            # through to its generic "Nothing found to reverse." message for
            # any unrecognized target_kind, which is the honest answer here:
            # neither kind had anything, so naming one would be misleading.
            return
        target_kind, target = found
        event.fields["target_kind"] = target_kind
        if target_kind == "transfer":
            event.fields["money_transaction_id"] = target["money_transaction_id"]
            event.fields["reversal_amount"] = target["amount"]
            event.fields["reversal_from_account_name"] = target["from_account_name"]
            event.fields["reversal_to_account_name"] = target["to_account_name"]
        else:
            event.fields["expense_id"] = target["expense_id"]
            event.fields["reversal_amount"] = target["amount"]
            event.fields["reversal_description"] = target["description"]
            event.fields["reversal_occurred_date"] = target["occurred_date"]
        return

    if target_kind == "transfer":
        transfer = await reversal_query.find_latest_transfer(organization_id=actor.organization_id)
        if transfer is not None:
            event.fields["money_transaction_id"] = transfer["money_transaction_id"]
            event.fields["reversal_amount"] = transfer["amount"]
            event.fields["reversal_from_account_name"] = transfer["from_account_name"]
            event.fields["reversal_to_account_name"] = transfer["to_account_name"]
        return

    expense = await reversal_query.find_latest_expense(
        organization_id=actor.organization_id, project_id=event.project_id, site_id=event.site_id
    )
    if expense is not None:
        event.fields["expense_id"] = expense["expense_id"]
        event.fields["reversal_amount"] = expense["amount"]
        event.fields["reversal_description"] = expense["description"]
        event.fields["reversal_occurred_date"] = expense["occurred_date"]


def _seed_account_admin_role(event: CanonicalEventV2, decision: PlannerDecisionV2, actor: ActorIdentity | None) -> None:
    """Feed the sender's role into the draft the same way
    _seed_account_candidates does for TRANSFER/PETTY_CASH -- defense-in-depth
    for application/finance/validation.py's role check. Not the primary
    gate: _account_admin_role_denied_reply (called before workflow_runtime.
    start(), see process_inbound_message) already refuses a disallowed role
    before a draft is ever built, so this only matters if that earlier gate
    is ever bypassed. Only ever runs for ACCOUNT_ADMIN. No I/O -- actor.role
    is already resolved, same as _seed_account_candidates's created_by_role."""
    if actor is None or decision.workflow_key is not WorkflowKey.ACCOUNT_ADMIN:
        return
    event.fields["created_by_role"] = actor.role


async def _seed_labour_query(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    labour_query_service: LabourQueryService | None,
    actor: ActorIdentity | None,
    timezone_name: str | None,
) -> None:
    """Answer the attendance question before the graph runs -- a node must
    never query a repository itself, same principle as
    _seed_finance_query_context above. Only ever runs for LABOUR_QUERY.

    The date range defaults to *today* rather than expense's "this month":
    the question a supervisor actually asks is "how many workers today", and
    attendance is a daily rhythm in a way spending is not.
    """
    if labour_query_service is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.LABOUR_QUERY:
        return

    # The sender's today, not the server's -- same UTC-vs-site-timezone trap
    # canonicalization/occurred_date.py exists to close. Asking "how many
    # workers today" at 2am in India must not answer for yesterday. The
    # timezone comes from resolved context (ActorIdentity doesn't carry one).
    today = today_for(timezone_name)
    start_date, end_date, date_range_label = resolve_labour_date_range(
        event.fields.get("date_range"), today=today
    )
    results = await labour_query_service.summarize_attendance(
        organization_id=actor.organization_id,
        project_id=event.project_id,
        site_id=event.site_id,
        start_date=start_date,
        end_date=end_date,
        trade=event.fields.get("trade"),
    )
    results["date_range_label"] = date_range_label
    event.fields["labour_results"] = results


async def _seed_activity_search(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    activity_search_service: ActivitySearchService | None,
    actor: ActorIdentity | None,
    timezone_name: str | None,
) -> None:
    """Answer #17 "what did I log / any open issues" before the graph runs --
    same shape and reasoning as _seed_labour_query above. Only ever runs for
    ACTIVITY_QUERY.

    Defaults to *today*, same reasoning as labour_query's default: the
    question a supervisor asks about their own site log is almost always
    about the current day, not a rolling window.
    """
    if activity_search_service is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.ACTIVITY_QUERY:
        return

    today = today_for(timezone_name)
    start_date, end_date, date_range_label = resolve_labour_date_range(
        event.fields.get("date_range"), today=today
    )
    results = await activity_search_service.search(
        organization_id=actor.organization_id,
        project_id=event.project_id,
        site_id=event.site_id,
        start_date=start_date,
        end_date=end_date,
        work_type=event.fields.get("work_type"),
    )
    results["date_range_label"] = date_range_label
    event.fields["activity_search_results"] = results


async def _seed_worker_candidates(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    workforce_query: WorkforceQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Feed the workforce register into the event so labour_update's
    match_workers node can decide whether a reported "Ravi" is someone
    already known -- a node must never query a repository itself (see
    workflows/runtime.py), same principle as _seed_account_candidates above.
    Only ever runs for LABOUR_ATTENDANCE.

    Skipped entirely when the report names nobody: an attendance of pure
    headcount groups ("12 helpers, 4 masons") has nothing to match, so
    reading the register would be work done to answer a question no one
    asked. This is the common case on many sites (principle P10), and it is
    also the fastest one -- keeping it free matters (P9).

    An empty register is a normal, correct outcome, not a failure: every
    named worker then resolves to a temporary worker and the workflow asks
    nothing (P3). The register is only ever read here -- attendance must
    never write it (P1).
    """
    if workforce_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.LABOUR_ATTENDANCE:
        return

    lines = event.fields.get("lines")
    if not isinstance(lines, list):
        return
    names_reported = any(
        isinstance(line, dict) and str(line.get("worker_name") or "").strip() for line in lines
    )
    if not names_reported:
        return

    candidates = await workforce_query.list_worker_candidates(
        organization_id=actor.organization_id,
        project_id=event.project_id,
        site_id=event.site_id,
    )
    if candidates:
        event.fields["worker_candidates"] = candidates


async def _maybe_trigger_worker_promotion(
    handled: InteractionHandled,
    workflow_runtime: WorkflowRuntime,
    workforce_query: WorkforceQueryService | None,
    actor: Any,
    wa_id: str,
    send_text_fn: Callable[[str, str], Awaitable[Any]],
    send_button_fn: Callable[[str, str, tuple], Awaitable[Any]] | None = None,
) -> None:
    """After a confirmed RECORD_LABOUR_ATTENDANCE execution, send a follow-up
    offer to add named temporary workers to the Worker Register.

    Fires only when:
    - The confirmed action type is RECORD_LABOUR_ATTENDANCE
    - The domain execution succeeded
    - At least one attendance line has a non-empty worker_name AND worker_id=None

    Nothing in the attendance workflow is changed. This is the optional second
    step (plan principle P1 + P9): attendance first, register management later.
    """
    # Guard: only after a successful RECORD_LABOUR_ATTENDANCE execution.
    if not isinstance(handled.result, WorkflowResumeResult):
        return
    if handled.result.status is not WorkflowResumeStatus.CONFIRMED:
        return
    confirmed = handled.result.confirmed_action
    if confirmed is None:
        return
    if confirmed.draft_action.action_type is not DraftActionType.RECORD_LABOUR_ATTENDANCE:
        return
    if handled.execution_result is None:
        return
    # Import here to avoid circular dependency at module load time.
    from mesiri_contracts.application.results.execution_result import ExecutionStatus
    if handled.execution_result.status is not ExecutionStatus.SUCCEEDED:
        return

    org_id = str(getattr(actor, "organization_id", None) or "")
    if not org_id:
        return

    # Extract named temporary workers from the confirmed attendance lines.
    lines = confirmed.draft_action.fields.get("lines") or []
    promotable: list[dict] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        name = str(line.get("worker_name") or "").strip()
        if not name:
            continue  # Headcount-only worker — never promote directly.
        if line.get("worker_id") is not None:
            continue  # Already matched to a registered worker — nothing to promote.
        promotable.append({
            "name": name,
            "trade": line.get("trade"),
            "daily_wage": line.get("daily_wage"),
        })

    if not promotable:
        return  # No new named temps — nothing to offer.

    # Build an existing-worker-ids set for the final duplicate guard inside the
    # promotion node. We reuse the candidate list from the attendance workflow's
    # collected_fields (already loaded into memory — no extra DB read needed).
    existing_ids: set[str] = set()
    if workforce_query is not None:
        # Fetch the register again — the attendance run may have finished within
        # the same second so an in-memory set from before is equally fresh, but
        # fetching again costs one read and prevents any race on a longer flow.
        try:
            candidates = await workforce_query.list_worker_candidates(
                organization_id=org_id,
                project_id=str(confirmed.draft_action.project_id or "") or None,
                site_id=str(confirmed.draft_action.site_id or "") or None,
            )
            existing_ids = {str(c["worker_id"]) for c in candidates}
        except Exception:  # noqa: BLE001 — promotion never blocks attendance
            existing_ids = set()

    # Inject the create_worker callable so the promotion node never touches
    # repositories directly (same isolation principle as _seed_worker_candidates).
    user_id = str(getattr(actor, "user_id", None) or confirmed.draft_action.user_id or "")
    user_id_for_create = user_id or None

    def _sync_create_worker(*, name: str, trade: str | None, daily_wage: object | None) -> None:
        """Synchronous shim called from inside a sync LangGraph node.

        The node runs inside graph.ainvoke(), but the LangGraph node itself is a
        sync function (matching every other node in this codebase). LangGraph
        runs sync nodes via run_in_executor(None, ...) -- a fresh
        ThreadPoolExecutor thread, which has no event loop of its own.
        asyncio.get_event_loop() would raise RuntimeError there ("no current
        event loop in thread"); asyncio.run() creates and tears down a loop
        local to this thread, which is exactly what's needed for one write.
        """
        import asyncio as _asyncio
        if workforce_query is None:
            return
        coro = workforce_query.create_worker(
            organization_id=org_id,
            name=name,
            trade=trade,
            daily_wage=daily_wage,
            created_by=user_id_for_create,
        )
        _asyncio.run(coro)

    # Synthetic decision + event to drive the promotion workflow through the
    # WorkflowRuntime (which handles COLLECTING_FIELDS persistence, provide_input
    # resume, and the single-active gate bypass for informational workflows).
    promotion_correlation_id = _new_id("promo")
    promotion_decision = PlannerDecisionV2(
        correlation_id=promotion_correlation_id,
        source_message_id=promotion_correlation_id,
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.WORKER_PROMOTION,
        reason=CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED,
        organization_id=confirmed.draft_action.organization_id,
        user_id=confirmed.draft_action.user_id,
        project_id=confirmed.draft_action.project_id,
        site_id=confirmed.draft_action.site_id,
    )
    promotion_event = CanonicalEventV2(
        event_id=promotion_correlation_id,
        correlation_id=promotion_correlation_id,
        source_message_id=promotion_correlation_id,
        event_type=CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED,
        completeness=_IntentCompleteness.ACTIONABLE,
        organization_id=confirmed.draft_action.organization_id,
        user_id=confirmed.draft_action.user_id,
        project_id=confirmed.draft_action.project_id,
        site_id=confirmed.draft_action.site_id,
        fields={
            "promotable_workers": promotable,
            "_existing_worker_ids": list(existing_ids),
            "_create_worker_fn": _sync_create_worker,
        },
    )

    try:
        promo_run = await workflow_runtime.start(promotion_decision, promotion_event)
    except Exception:  # noqa: BLE001 — promotion failure never blocks or retries
        _log.warning("worker_promotion.start_failed org=%s", org_id)
        return

    # Pass 1 result: the promotion node ran, built the offer message, and
    # saved the state as COLLECTING_FIELDS waiting for the user's choice.
    if promo_run.pending_prompt:
        await _safe(send_text_fn(wa_id, promo_run.pending_prompt))


async def _seed_duplicate_check(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    duplicate_expense_query: DuplicateExpenseQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Finance Module Slice 8: flag a likely-duplicate expense before the
    graph runs (a node must never query a repository itself, same principle
    as _seed_account_candidates above). Only ever runs for EXPENSE_SUBMIT.
    No signal beyond amount+date alone is strong enough, so this is skipped
    entirely when neither vendor nor category was extracted -- see
    runtime/duplicate_expense_query.py."""
    if duplicate_expense_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.EXPENSE_SUBMIT:
        return
    amount = event.fields.get("amount")
    vendor_name = event.fields.get("vendor")
    category_name = event.fields.get("category")
    if amount is None or not (vendor_name or category_name):
        return
    is_duplicate = await duplicate_expense_query.find_potential_duplicate(
        organization_id=actor.organization_id,
        project_id=event.project_id,
        amount=amount,
        vendor_name=vendor_name,
        category_name=category_name,
    )
    if is_duplicate:
        event.fields["is_potential_duplicate"] = True


async def _seed_vendor_check(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    vendor_query: VendorQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Flag a vendor name that doesn't match any existing active vendor
    before the graph runs (a node must never query a repository itself, same
    principle as _seed_account_candidates above). Only ever runs for
    EXPENSE_SUBMIT, and only when a vendor was actually extracted --
    otherwise there is nothing to confirm and expense_capture's build_draft
    proceeds vendor-less exactly as before. See workflows/expense_capture/
    nodes.py's `resolve_vendor`."""
    if vendor_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.EXPENSE_SUBMIT:
        return
    vendor_name = event.fields.get("vendor")
    if not vendor_name:
        return
    matched = await vendor_query.exists(
        organization_id=actor.organization_id, vendor_name=str(vendor_name)
    )
    if not matched:
        event.fields["vendor_needs_confirmation"] = True


async def _seed_open_activity(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    activity_query: ActivityQueryService | None,
    actor: ActorIdentity | None,
    *,
    remembered_activity_id: str | None = None,
) -> None:
    """Resolve which Activity a continuation message ("finished plastering",
    "completed another 40 sqm") is about, before the graph runs (a node must
    never query a repository itself, same principle as
    _seed_account_candidates above). Only ever runs for
    WorkflowKey.ACTIVITY_CONTINUATION.

    ``remembered_activity_id`` (memory/conversation_scope.py's
    CurrentActivityStore -- the activity THIS conversation most recently
    touched) is tried first and, if it's still open, wins outright: it is
    strictly better evidence than "most recently updated on this site",
    which can't tell two engineers' simultaneous activities apart. It is
    revalidated against Postgres before use (a memory hint is never
    authoritative -- see memory/requirements.py) and falls through to the
    site-wide lookup below on any miss, so a stale/completed remembered
    activity degrades to the existing V1 behaviour rather than erroring.

    Seeds `activity_id` (+ `activity_summary` for the confirmation prompt) if
    exactly one open activity is found. Otherwise leaves fields untouched --
    workflows/activity_continuation/nodes.py's `build_draft` checks for a
    missing `activity_id` and ends the pass with a clarifying message and no
    draft (P1: there is nothing to append a Progress Update onto), rather
    than persisting anything against a guess.
    """
    if activity_query is None or actor is None or not actor.organization_id:
        return
    if decision.workflow_key is not WorkflowKey.ACTIVITY_CONTINUATION:
        return

    found: dict | None = None
    if remembered_activity_id:
        found = await activity_query.get_activity_if_open(
            organization_id=actor.organization_id, activity_id=remembered_activity_id
        )
    if found is None:
        found = await activity_query.find_open_activity(
            organization_id=actor.organization_id,
            site_id=event.site_id,
            reported_by_user_id=actor.user_id,
        )
    if found is None:
        return
    event.fields["activity_id"] = found["activity_id"]
    summary_bits = [b for b in (found.get("work_type"), found.get("narrative")) if b]
    if summary_bits:
        event.fields["activity_summary"] = " — ".join(summary_bits)


async def _seed_finance_query_context(
    event: CanonicalEventV2,
    decision: PlannerDecisionV2,
    money_account_query: MoneyAccountQueryService | None,
    expense_query_service: ExpenseQueryService | None,
    actor: ActorIdentity | None,
) -> None:
    """Feed resolved balance/expense data into the event's fields for
    Finance Module Slice 2's read-only query workflows -- same principle as
    _seed_account_candidates above: a node must never query a repository
    itself, so this is the seeding point. Runs only for
    ACCOUNT_BALANCE_QUERY / EXPENSE_QUERY; every other workflow key's
    fields are left untouched."""
    if actor is None or not actor.organization_id:
        return

    if decision.workflow_key is WorkflowKey.ACCOUNT_BALANCE_QUERY:
        if money_account_query is None:
            return
        account_name = event.fields.get("account_name")
        accounts = await money_account_query.find_matching_accounts(
            organization_id=actor.organization_id,
            created_by=actor.user_id,
            account_name=account_name,
        )
        balances = await money_account_query.get_balances(
            organization_id=actor.organization_id, accounts=accounts
        )
        event.fields["balance_results"] = [
            {"name": account.name, "balance": str(balances[account.id])} for account in accounts
        ]
        return

    if decision.workflow_key is WorkflowKey.EXPENSE_QUERY:
        if expense_query_service is None:
            return
        category_name = event.fields.get("category_name")
        missing_receipts_only = bool(event.fields.get("missing_receipts"))
        start_date, end_date, date_range_label = resolve_date_range(event.fields.get("date_range"))
        expenses = await expense_query_service.list_expenses(
            organization_id=actor.organization_id,
            project_id=event.project_id,
            site_id=event.site_id,
            start_date=start_date,
            end_date=end_date,
            category_name=category_name,
            missing_receipts_only=missing_receipts_only,
        )
        event.fields["expense_results"] = {
            "total": str(ExpenseQueryService.total(expenses)),
            "count": len(expenses),
            "date_range_label": date_range_label,
            "items": [
                {
                    "amount": str(expense.amount),
                    "description": expense.description,
                    "occurred_date": expense.occurred_date.isoformat(),
                }
                for expense in expenses
            ],
        }


async def _plan_and_run(
    event: CanonicalEventV2,
    *,
    planner: Planner,
    workflow_runtime: WorkflowRuntime,
    inventory_query: MaterialInventoryQueryService | None = None,
    pending_report_store: PendingReportStore | None = None,
    actor_user_id: str | None = None,
) -> ReplySpec | None:
    """Run the planner and, if it starts a workflow, the workflow -- shared by
    every resume_pending_report_with_* function, so a resumed report goes
    through the exact same decision path a first-pass ACTIONABLE report
    would (see _inject_inventory_context for why inventory context is
    injected here rather than at canonicalization time).

    Also re-runs the stock sufficiency gate (_run_stock_gate) right after
    inventory context is injected, same as the first-pass journey -- a
    material-picker or unit-mismatch tap can be the leg that first makes a
    usage report ACTIONABLE, so the over-stock check can't only live before
    those gates."""
    await _inject_inventory_context(event, inventory_query)
    if pending_report_store is not None and actor_user_id is not None:
        stock_reply = await _run_stock_gate(
            event, pending_report_store=pending_report_store, actor_user_id=actor_user_id
        )
        if stock_reply is not None:
            return stock_reply
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
    org_settings_query: OrganizationSettingsQueryService | None = None,
    expense_category_query: ExpenseCategoryQueryService | None = None,
    money_account_query: MoneyAccountQueryService | None = None,
    petty_cash_query: PettyCashRecipientQueryService | None = None,
    reversal_query: ReversalTargetQueryService | None = None,
    duplicate_expense_query: DuplicateExpenseQueryService | None = None,
    workforce_query: WorkforceQueryService | None = None,
    labour_query_service: LabourQueryService | None = None,
    vendor_query: VendorQueryService | None = None,
    expense_query_service: ExpenseQueryService | None = None,
    activity_query: ActivityQueryService | None = None,
    activity_search_service: ActivitySearchService | None = None,
    semantic_hint: str | None = None,
    direction_hint: str | None = None,
    pending_report_store: PendingReportStore | None = None,
    category_hint_store: CategoryHintStore | None = None,
    memory_loader: ConversationMemoryLoader | None = None,
    memory_coordinator: ConversationMemoryCoordinator | None = None,
    batch_store: PendingBatchStore | None = None,
    escalation_query: EscalationCreateService | None = None,
) -> JourneyResult:
    mlog: MessageLogger = message_logger or NoopMessageLogger()
    tlog: TraceLogger = trace_logger or NoopTraceLogger()
    correlation_id = message.correlation_id

    # M19 conversation memory: loaded concurrently with understanding below
    # (independent reads -- see memory/context_loader.py's own docstring for
    # why this mirrors context/resolver.py's gather pattern). None whenever
    # the container didn't wire it (tests, or memory_loader not yet built) --
    # every consumer below already treats a None pack as "no opinion".
    memory_pack: ContextPack | None = None
    memory_pack_task: asyncio.Task[ContextPack] | None = None
    if memory_loader is not None and actor is not None and actor.organization_id:
        memory_pack_task = asyncio.ensure_future(
            memory_loader.load(organization_id=actor.organization_id, user_id=actor_user_id)
        )

    # --- Understanding stage ---
    t0 = time.perf_counter()
    try:
        expense_categories: list[str] | None = None
        if expense_category_query is not None and actor is not None and actor.organization_id:
            expense_categories = await expense_category_query.list_active_category_names(
                organization_id=actor.organization_id, created_by=actor.user_id
            )
        # Recorded separately from the AI work below: a traced image message
        # showed a 10.2s `understanding` stage whose provider calls only
        # accounted for ~7.1s, and this category lookup is the one database
        # round trip hiding inside the same measurement.
        categories_ms = int((time.perf_counter() - t0) * 1000)
        understanding = await pipeline.understand(
            message, semantic_hint=semantic_hint, expense_categories=expense_categories
        )
        await _safe(
            tlog.log_stage(
                correlation_id=correlation_id,
                stage="understanding",
                stage_payload={
                    **understanding.model_dump(mode="json"),
                    "expense_categories_ms": categories_ms,
                },
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

        # Low-confidence routing (#7) -- classified here, off understanding
        # alone, deliberately outside canonicalization (see
        # planner/ambiguity.py's module docstring for why). PROCEED is the
        # overwhelming common case and costs one pure-function call; the
        # caveat (if any) is applied later, only onto a confirmation prompt
        # the user is already about to read (see the reply-assembly step
        # near the end of this function). ESCALATE has no receiving domain
        # in this slice yet (#10 Human Review) -- logged as the documented
        # extension point rather than silently dropped.
        ambiguity_decision = decide_ambiguity(understanding)
        if ambiguity_decision.action is AmbiguityAction.ESCALATE:
            _log.warning(
                "ambiguity.escalate correlation_id=%s reason=%s",
                correlation_id,
                ambiguity_decision.reason,
            )
            # #10 Human Review: a durable review record, not a re-triggerable
            # draft -- there is no workflow, no context resolution, and
            # often no organization_id yet at this point (ESCALATE fires
            # right off understanding, before context resolution runs
            # below), so the snapshot captures what understanding itself
            # saw. Fire-and-forget: creating the review record must never
            # delay or fail the reply the user still gets this turn.
            if escalation_query is not None and actor is not None and actor.organization_id:
                asyncio.ensure_future(
                    escalation_query.create(
                        organization_id=actor.organization_id,
                        correlation_id=correlation_id,
                        reason=ambiguity_decision.reason,
                        snapshot={
                            "modality": understanding.input_modality.value,
                            "semantic_type": understanding.semantic_type.value,
                            "transcript": understanding.transcript,
                            "normalized_text": understanding.normalized_text,
                            "translated_text": understanding.translated_text,
                            "overall_confidence": understanding.overall_confidence.value,
                            "missing_fields": understanding.missing_fields,
                            "warnings": understanding.warnings,
                        },
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
            # Phase 4: send confirmation text FIRST so the user sees it
            # immediately, then render the receipt PNG and send the image.
            await send_text(message.sender.wa_id, handled.reply_text)
            if handled.receipt_coro is not None and send_image is not None:
                try:
                    image_bytes = await handled.receipt_coro
                except Exception:  # noqa: BLE001 -- receipt failure must never drop the message
                    image_bytes = None
                if image_bytes is not None:
                    await send_image(message.sender.wa_id, image_bytes, caption=None)
            # Worker promotion follow-up: fires only after a successful
            # RECORD_LABOUR_ATTENDANCE with new named temporary workers.
            # Attendance text + receipt are already sent above — this is
            # strictly a second-step offer that never delays the reply.
            await _safe(
                _maybe_trigger_worker_promotion(
                    handled,
                    workflow_runtime,
                    workforce_query,
                    actor,
                    message.sender.wa_id,
                    send_text,
                    send_button_fn=send_button,
                )
            )
            await _safe(mlog.log_reply(correlation_id=correlation_id, reply=handled.reply_text))
            if handled.result.workflow_instance_id:
                await _safe(
                    mlog.link_workflow_instance(
                        correlation_id=correlation_id,
                        workflow_instance_id=handled.result.workflow_instance_id,
                    )
                )

            if isinstance(handled.result, WorkflowRunResult):
                workflow_run = handled.result
            else:
                workflow_resume = handled.result

            if not handled.unrelated_text:
                await _safe(
                    mlog.update_context(
                        correlation_id=correlation_id,
                        project_id=handled.project_id,
                        site_id=handled.site_id,
                    )
                )
                await _safe(mlog.mark_completed(correlation_id=correlation_id))
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
            # #1 Multi-Activity / #13 Cross-Module Trigger: build_canonical_events
            # (plural) may return more than one segment for a single message
            # (see canonicalization/builder.py's docstring for exactly which
            # cases, and which it does not yet cover). canonical_event stays
            # bound to events[0] for every line below, completely unchanged
            # from before this existed -- extra_segments (queued after the
            # primary workflow starts, see the workflow stage below) is the
            # only new state this introduces into the first-pass journey.
            canonical_events = build_canonical_events(
                understanding,
                resolved,
                direction_hint=direction_hint,
                # Meta's forwarding markers, recorded at ingress. Read from
                # metadata rather than re-derived: normalization is the only
                # layer that sees Meta's raw `context` object.
                forwarded=bool(message.metadata.get("forwarded")),
                frequently_forwarded=bool(message.metadata.get("frequently_forwarded")),
            )
            canonical_event = canonical_events[0]
            extra_segments = canonical_events[1:]

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

            # inventory_levels (for INVENTORY_QUERY_ASKED) and available_stock
            # (for MATERIAL_USAGE_REQUESTED's low-stock warning) are injected
            # in _plan_and_run instead of here -- project_id/site_id can still
            # change after this point (material/unit/project/site gates below
            # all run after canonicalization), so computing them this early
            # used to bake in whatever scope was resolved *before* any gate
            # asked a clarifying question, silently answering for the wrong
            # project/site once the user picked one. _plan_and_run runs after
            # every gate has settled, on both the first pass and every
            # resume_pending_report_with_* path, so it's the one place
            # guaranteed to see the final project_id/site_id.

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
            # Self-tag: this message IS the origin of whatever interaction
            # follows (a material/unit/project gate hold, or a workflow start
            # further down). _complete_resume_leg re-reads this same
            # canonical_event.correlation_id on every later gate-resume leg,
            # so tagging it here is what lets a multi-turn report (voice note
            # -> material pick -> unit confirm -> project pick -> workflow
            # confirm) resolve to one interaction in the logs viewer.
            await _safe(
                mlog.set_interaction_group(
                    correlation_id=correlation_id, group_id=canonical_event.correlation_id
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
                actor_role=actor.role if actor is not None else None,
                org_settings_query=org_settings_query,
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

        # --- Site-selection gate ---
        # Once project is settled, a report/query can still be ambiguous
        # across the project's sites. Inventory queries offer "All Sites
        # Combined" (allow_combined=True); a material report being recorded
        # always has to land on one real site, so recording never offers
        # that option. See _run_site_gate for the single/zero-site shortcuts.
        if held_reply is None and pending_report_store is not None:
            held_reply = await _run_site_gate(
                canonical_event,
                actor=actor,
                actor_user_id=actor_user_id,
                pending_report_store=pending_report_store,
                allow_combined=canonical_event.event_type
                is CanonicalEventType.INVENTORY_QUERY_ASKED,
            )

        if held_reply is None:
            await _inject_inventory_context(canonical_event, inventory_query)

            # --- Stock sufficiency gate ---
            # Usage quantity vs available stock can only be checked once
            # available_stock is injected above -- block instead of letting
            # an over-limit usage through to the old cosmetic-only warning
            # (see _run_stock_gate).
            if pending_report_store is not None:
                held_reply = await _run_stock_gate(
                    canonical_event,
                    pending_report_store=pending_report_store,
                    actor_user_id=actor_user_id,
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
                    if memory_pack_task is not None:
                        try:
                            memory_pack = await memory_pack_task
                        except Exception:  # noqa: BLE001 -- memory is a hint, never load-bearing
                            _log.warning(
                                "memory.pack_load_failed correlation_id=%s",
                                correlation_id,
                                exc_info=True,
                            )
                    # Run all 10 seed functions in parallel — each targets a
                    # different table and is fully independent of the others.
                    timezone_name = resolved.timezone if resolved else None
                    await asyncio.gather(
                        _seed_account_candidates(
                            canonical_event, planner_decision, money_account_query, actor
                        ),
                        _seed_petty_cash_recipient(
                            canonical_event, planner_decision, petty_cash_query, actor
                        ),
                        _seed_reversal_target(
                            canonical_event, planner_decision, reversal_query, actor
                        ),
                        _seed_worker_candidates(
                            canonical_event, planner_decision, workforce_query, actor
                        ),
                        _seed_duplicate_check(
                            canonical_event, planner_decision, duplicate_expense_query, actor
                        ),
                        _seed_vendor_check(
                            canonical_event, planner_decision, vendor_query, actor
                        ),
                        _seed_finance_query_context(
                            canonical_event,
                            planner_decision,
                            money_account_query,
                            expense_query_service,
                            actor,
                        ),
                        _seed_open_activity(
                            canonical_event,
                            planner_decision,
                            activity_query,
                            actor,
                            remembered_activity_id=(
                                memory_pack.current_activity_id if memory_pack else None
                            ),
                        ),
                        # LABOUR_QUERY was defined but never wired into this
                        # gather -- every attendance question silently
                        # answered "no attendance recorded" regardless of
                        # what was actually logged, since generate_labour_
                        # query_reply reads collected_fields['labour_results']
                        # and nothing ever populated it. Fixed alongside #17
                        # Search/Ask Mesiri, which follows this exact
                        # seed-before-graph pattern and would have inherited
                        # the same silent-no-op bug if copied uncorrected.
                        _seed_labour_query(
                            canonical_event,
                            planner_decision,
                            labour_query_service,
                            actor,
                            timezone_name,
                        ),
                        _seed_activity_search(
                            canonical_event,
                            planner_decision,
                            activity_search_service,
                            actor,
                            timezone_name,
                        ),
                    )
                    # Synchronous — not a coroutine, runs after the gather.
                    _seed_account_admin_role(canonical_event, planner_decision, actor)

                    # Account-admin role gate: refused before the workflow
                    # even starts (no draft, no confirmation prompt) --
                    # "should not even be an option" for a disallowed role,
                    # not merely rejected after they complete a confirm
                    # flow (unlike TRANSFER, which only gates at confirm
                    # time -- see transfer_validation.py's docstring for why
                    # that's an accepted tradeoff there but not here).
                    # application/finance/validation.py's role check (fed by
                    # _seed_account_admin_role above) is the defense-in-depth
                    # backstop if this is ever bypassed.
                    if (
                        planner_decision.workflow_key is WorkflowKey.ACCOUNT_ADMIN
                        and str(getattr(actor, "role", None) or "").strip().upper()
                        not in _ACCOUNT_ADMIN_ROLES
                    ):
                        await send_text(message.sender.wa_id, _ACCOUNT_ADMIN_DENIED_REPLY)
                        await _safe(
                            mlog.log_reply(
                                correlation_id=correlation_id, reply=_ACCOUNT_ADMIN_DENIED_REPLY
                            )
                        )
                        await _safe(mlog.mark_completed(correlation_id=correlation_id))
                        return JourneyResult(
                            understanding=understanding,
                            resolved_context=resolved,
                            canonical_event=canonical_event,
                            planner_decision=planner_decision,
                            workflow_run=None,
                        )

                    workflow_run = await workflow_runtime.start(planner_decision, canonical_event)

                    # #1 Multi-Activity / #13 Cross-Module Trigger: the
                    # primary segment started normally above -- the
                    # single-active invariant is untouched, exactly as if
                    # this were an ordinary one-segment message. If there
                    # ARE extra segments, queue them and caption this
                    # prompt with its batch position; the rest run one at a
                    # time as each prior segment's confirmation resolves
                    # (interactions/handler.py -> workflows/batch.py).
                    if (
                        extra_segments
                        and workflow_run.status is WorkflowRunStatus.STARTED
                        and batch_store is not None
                    ):
                        total = 1 + len(extra_segments)
                        await batch_store.start_batch(
                            user_id=actor_user_id, remaining=extra_segments, total=total
                        )
                        workflow_run = dataclasses.replace(
                            workflow_run,
                            pending_prompt=format_batch_prefix(
                                BatchProgress(index=1, total=total, outcomes=())
                            )
                            + (workflow_run.pending_prompt or ""),
                        )

                    if context_debug:
                        log_workflow_run(workflow_run)
                    if workflow_run.workflow_instance_id:
                        await _safe(
                            mlog.link_workflow_instance(
                                correlation_id=correlation_id,
                                workflow_instance_id=workflow_run.workflow_instance_id,
                            )
                        )
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

    # Attach the low-confidence caveat (if any) ONLY to a freshly-started
    # confirmation for THIS message (workflow_run.status STARTED). Never on
    # held_reply (a gate prompt is asking about something else entirely) and
    # never on BLOCKED_PENDING_CONFIRMATION (that prompt describes an OLDER
    # draft this message didn't produce -- captioning it with this message's
    # own field confidence would name the wrong report).
    if (
        held_reply is None
        and reply is not None
        and workflow_run is not None
        and workflow_run.status is WorkflowRunStatus.STARTED
    ):
        caveat = caveat_text(ambiguity_decision)
        if caveat:
            reply = ReplySpec(
                text=f"{caveat}\n\n{reply.text}",
                list_button_label=reply.list_button_label,
                list_rows=reply.list_rows,
                buttons=reply.buttons,
            )

    if reply is not None:
        send_result = await send_reply_spec(
            reply,
            message.sender.wa_id,
            send_text=send_text,
            send_list=send_list,
            send_button=send_button,
        )
        await _safe(mlog.log_reply(correlation_id=correlation_id, reply=reply.text))
        # #11 Reply Workflow: only the plain-text branch of send_reply_spec
        # returns a wamid (see that module's docstring) -- a str result
        # means the reply was captured; anything else (bool from the list/
        # button branches, or None on send failure) means there is nothing
        # to record.
        if isinstance(send_result, str):
            await _safe(
                mlog.set_reply_wamid(correlation_id=correlation_id, reply_wamid=send_result)
            )

    await _safe(mlog.mark_completed(correlation_id=correlation_id))

    if memory_coordinator is not None:
        user_text = understanding.transcript or understanding.normalized_text or ""
        asyncio.ensure_future(
            memory_coordinator.record_turn(
                user_id=actor_user_id,
                user_text=user_text,
                assistant_reply=reply.text if reply is not None else "",
                correlation_id=correlation_id,
            )
        )

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
