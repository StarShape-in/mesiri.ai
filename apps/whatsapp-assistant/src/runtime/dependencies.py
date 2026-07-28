"""Application dependency wiring for the WhatsApp assistant runtime."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import MetaMediaDownloader
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver
from interactions.image_purpose import try_hold_new_image_for_purpose_picker
from runtime.account_admin_journey import try_handle_account_admin_command
from runtime.logging_ports import MessageLogger, TraceLogger
from runtime.step_timing import StepTimer

if TYPE_CHECKING:
    from backend.ports import ActorReader
    from channel.receipt import ReceiptRenderer
    from context.resolver import ContextResolver
    from interactions import InteractionHandler
    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri_contracts.common.storage import ObjectStoragePort
    from planner import Planner
    from runtime.expense_category_query import ExpenseCategoryQueryService
    from runtime.inventory_query import MaterialInventoryQueryService
    from runtime.material_catalog_query import MaterialCatalogQueryService
    from runtime.org_settings_query import OrganizationSettingsQueryService
    from understanding.pipeline import UnderstandingPipeline
    from workflows import WorkflowRuntime


class Settings(BaseSettings):
    """Environment-backed configuration for WhatsApp ingress."""

    verify_token: str
    app_secret: str
    access_token: str
    phone_number_id: str = ""
    api_version: str = "v21.0"
    graph_base_url: str = "https://graph.facebook.com"
    dedup_ttl_hours: int = 24
    context_debug: bool = False

    model_config = SettingsConfigDict(
        env_prefix="WHATSAPP_",
        env_file=".env",
        extra="ignore",
    )


@dataclass(slots=True)
class AppContainer:
    """Process-scoped dependency container."""

    settings: Settings
    http_client: httpx.AsyncClient
    deduplication_store: InMemoryDeduplicationStore
    message_store: InMemoryNormalizedMessageStore
    receiver: WhatsAppReceiver
    context_resolver: ContextResolver
    # The understanding pipeline (STT/vision/extraction). Held on the container
    # so out-of-band callers (e.g. the control-plane test harness in
    # admin/system_graph_router.py) can run process_inbound_message without
    # re-wiring providers; the webhook path uses the same instance.
    pipeline: UnderstandingPipeline
    planner: Planner
    workflow_runtime: WorkflowRuntime
    interaction_handler: InteractionHandler
    # Identity gate reader (M4). Exposed for the same reason as `pipeline` --
    # the control-plane test harness (admin/system_graph_router.py) replays
    # the exact same pre-pipeline fast-path order as _on_normalized below,
    # which starts with resolve_sender(actor_reader, wa_id).
    actor_reader: ActorReader
    # Read-only inventory lookups for the material.inventory_query workflow.
    # Exposed for the same reason as pipeline/actor_reader above.
    inventory_query: MaterialInventoryQueryService
    # Read-only catalog/units-of-measure lookups for the material/unit
    # resolution gate. Exposed for the same reason as inventory_query above.
    catalog_query: MaterialCatalogQueryService
    # Per-org tunable rules (e.g. which roles may add a material to the
    # catalog from WhatsApp). Exposed for the same reason as catalog_query.
    org_settings_query: OrganizationSettingsQueryService
    # Read-only expense category names for the extraction call's AI-side
    # category selection. Exposed for the same reason as catalog_query above.
    expense_category_query: ExpenseCategoryQueryService
    # Resolves receipt/attachment object keys into presigned URLs for the
    # dashboard's expense-attachment endpoints (backend/src/mesiri/
    # infrastructure/objectstorage/dependency.py's get_object_storage falls
    # back to `request.app.state.container.object_storage`, since this is
    # the actual production app -- see runtime/lifecycle.py -- not
    # backend/src/mesiri/http/app.py). Was already built here (used for
    # build_pipeline/WhatsAppReceiver below) but never exposed on the
    # container itself, so every attachment fetch 500'd with AttributeError.
    object_storage: ObjectStoragePort
    # Owns the one headless-Chromium instance used to render post-confirmation
    # receipt images (see channel/receipt/). close() is called by the
    # lifespan handler, same lifecycle pattern as material_db/redis_client.
    receipt_renderer: ReceiptRenderer
    # redis_client is either a real RedisClient (when MESIRI_REDIS__HOST is set)
    # or FakeRedis for local/test.  Both expose connect() / disconnect() so the
    # lifespan handler can manage the lifecycle without special-casing.
    redis_client: Any
    message_logger: MessageLogger
    trace_logger: TraceLogger
    # M8: owns the one transaction Material command execution runs in. connect()/
    # disconnect() are called by the lifespan handler, same as redis_client.
    material_db: PostgresDatabase


def build_container(settings: Settings, http_client: httpx.AsyncClient) -> AppContainer:
    """Construct the application dependency container."""
    deduplication_store = InMemoryDeduplicationStore(ttl=timedelta(hours=settings.dedup_ttl_hours))
    message_store = InMemoryNormalizedMessageStore()
    media_downloader = MetaMediaDownloader(
        client=http_client,
        access_token=settings.access_token,
        api_version=settings.api_version,
        graph_base_url=settings.graph_base_url,
    )

    # M4 identity gate, then M2 -> M3 -> M4 Context resolver -> reply.
    import logging as _logging

    from backend.postgres.actor import PostgresActorReader
    from backend.postgres.message_logger import PostgresMessageLogger
    from backend.postgres.trace_logger import PostgresTraceLogger
    from backend.postgres.workflow_instance import PostgresWorkflowInstanceRepository
    from channel.replies import (
        CATEGORY_SEMANTIC_HINT,
        SILENTLY_IGNORED_RAW_TYPES,
        render_unsupported_media_reply,
    )
    from channel.whatsapp.outbound import WhatsAppSender
    from context.live_identity import (
        NO_ORG_MESSAGE,
        ORG_SUSPENDED_MESSAGE,
        UNREGISTERED_MESSAGE,
        resolve_sender,
    )
    from context.runtime import build_context_resolver
    from interactions import build_interaction_handler
    from interactions.category_hint import CategoryHintStore
    from interactions.pending_report import PendingReportStore
    from mesiri.application.materials.dispatcher import MaterialExecutionDispatcher
    from mesiri.application.materials.handlers import ExecuteConfirmedMaterialActionHandler
    from mesiri.application.materials.resolution import PostgresMaterialResolver
    from mesiri.bootstrap.settings import get_settings as _get_backend_settings
    from mesiri.infrastructure.objectstorage import build_object_storage
    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from mesiri.infrastructure.postgres.repositories.material_execution import (
        PostgresMaterialExecutionRepository,
    )
    from mesiri_ai.undo_classifier import UNDO_SEMANTIC_HINT, is_undo_trigger
    from mesiri_contracts.assistant.enums import InputModality
    from planner import Planner

    # See _send_processing_ack below. text/interactive deliberately absent --
    # they already reply in under ~2s (measured), where a second message
    # would just add noise.
    _PROCESSING_ACK_TEXT: dict[InputModality, str] = {
        InputModality.IMAGE: "📷 Got your photo — reading it now...",
        InputModality.DOCUMENT: "📄 Got your document — reading it now...",
        InputModality.VOICE: "🎤 Got your voice note — listening now...",
    }
    from runtime.inbound_journey import (
        process_inbound_message,
        resume_pending_report_with_material,
        resume_pending_report_with_material_create,
        resume_pending_report_with_material_unit_choice,
        resume_pending_report_with_project,
        resume_pending_report_with_site,
        resume_pending_report_with_stock_choice,
        resume_pending_report_with_unit,
    )
    from runtime.reply_dispatch import send_reply_spec
    from understanding.runtime import build_pipeline
    from workflows import WorkflowRegistry, WorkflowRuntime

    _log = _logging.getLogger("mesiri.context")

    # Object storage: FakeObjectStorage locally, R2 when
    # MESIRI_OBJECT_STORAGE__PROVIDER=r2 is set.
    #
    # Wrapped so a photo isn't fetched back out of R2 immediately after being
    # written to it: ingress downloads the bytes from Meta, uploads them, and
    # then understanding/pipeline.py's _read_media reads the very same key
    # again to hand to the vision/speech provider. The decorator answers that
    # one read from memory and drops the entry; every other call, and any
    # later read (e.g. the admin replay path), goes straight through to the
    # real adapter. See recent_writes_cache.py.
    from mesiri.infrastructure.objectstorage.recent_writes_cache import (
        RecentWritesCachingObjectStorage,
    )

    _backend_settings = _get_backend_settings()
    object_storage = RecentWritesCachingObjectStorage(build_object_storage(_backend_settings))

    # Redis for the active context store.  Use a real RedisClient when
    # MESIRI_REDIS__HOST is explicitly configured; fall back to FakeRedis.
    if os.environ.get("MESIRI_REDIS__HOST"):
        from mesiri.infrastructure.redis.client import RedisClient

        redis_client = RedisClient(_backend_settings.redis)
    else:
        from mesiri.infrastructure.redis.client import FakeRedis

        redis_client = FakeRedis()

    # Ephemeral category-tap hint (see interactions/category_hint.py) -- same
    # redis_client as the active context store, never authoritative.
    category_hint_store = CategoryHintStore(redis_client)
    # Holds a report awaiting a project pick (see interactions/pending_report.py
    # and runtime/inbound_journey.py's project-selection gate) -- same
    # redis_client, same never-authoritative principle.
    pending_report_store = PendingReportStore(redis_client)
    # Holds a genuinely new image awaiting "what is this photo for?" (see
    # interactions/pending_media.py and interactions/image_purpose.py) --
    # same redis_client, same never-authoritative principle.
    from interactions.pending_media import PendingMediaStore

    pending_media_store = PendingMediaStore(redis_client)

    # M8: the one transaction Material command execution runs in. connect()/
    # disconnect() happen in the lifespan handler (runtime/lifecycle.py), same
    # lifecycle pattern as redis_client.
    material_db = PostgresDatabase(_backend_settings.postgres)

    pipeline = build_pipeline(object_storage, material_db, redis_client)
    context_resolver = build_context_resolver(redis=redis_client)
    planner = Planner()  # stateless — safe to construct once and share
    # WorkflowRegistry compiles each graph once and caches it — constructed
    # once here, never per message.
    workflow_registry = WorkflowRegistry()
    workflow_runtime = WorkflowRuntime(
        registry=workflow_registry, repo=PostgresWorkflowInstanceRepository()
    )
    material_execution_handler = ExecuteConfirmedMaterialActionHandler(
        db=material_db,
        repo=PostgresMaterialExecutionRepository(),
        resolver=PostgresMaterialResolver(),
    )
    material_dispatcher = MaterialExecutionDispatcher(material_execution_handler)
    # Expense capture (M9): same in-process capability-boundary wiring as
    # Materials above, reusing the same material_db transaction pool. The
    # resolver turns the free-text `category` collected in conversation into
    # an expense_categories.id at confirmation time (defense-in-depth,
    # mirrors PostgresMaterialResolver).
    from mesiri.application.expenses.dispatcher import ExpenseExecutionDispatcher
    from mesiri.application.expenses.handlers import RecordExpenseHandler
    from mesiri.application.expenses.resolution import PostgresExpenseCategoryResolver
    from mesiri.application.vendors.resolution import PostgresVendorResolver
    from mesiri.infrastructure.postgres.repositories.expense_execution import (
        PostgresExpenseExecutionRepository,
    )

    expense_execution_handler = RecordExpenseHandler(
        PostgresExpenseExecutionRepository(),
        db=material_db,
        resolver=PostgresExpenseCategoryResolver(),
        vendor_resolver=PostgresVendorResolver(),
    )
    expense_dispatcher = ExpenseExecutionDispatcher(expense_execution_handler)
    # Account admin (Finance Module Slice 6, account-admin scope): same
    # in-process capability-boundary wiring as Expenses above. The resolver
    # finds the existing account by name for rename/deactivate, or checks
    # for a name collision on create.
    from mesiri.application.finance.dispatcher import AccountAdminExecutionDispatcher
    from mesiri.application.finance.handlers import ManageMoneyAccountHandler
    from mesiri.application.finance.resolution import PostgresAccountLookupResolver
    from mesiri.infrastructure.postgres.repositories.account_admin_execution import (
        PostgresAccountAdminExecutionRepository,
    )

    account_admin_execution_handler = ManageMoneyAccountHandler(
        PostgresAccountAdminExecutionRepository(),
        db=material_db,
        resolver=PostgresAccountLookupResolver(),
    )
    account_admin_dispatcher = AccountAdminExecutionDispatcher(account_admin_execution_handler)
    # Transfers (Finance Module Slice 3): same in-process capability-boundary
    # wiring as account admin above. The resolver re-verifies both accounts
    # are still active at confirm time -- the WhatsApp workflow already
    # resolved from/to to real account ids during slot-fill, so this is
    # defense-in-depth, not name resolution.
    from mesiri.application.finance.transfer_dispatcher import TransferExecutionDispatcher
    from mesiri.application.finance.transfer_handler import TransferMoneyHandler
    from mesiri.application.finance.transfer_resolution import PostgresTransferAccountResolver
    from mesiri.infrastructure.postgres.repositories.transfer_execution import (
        PostgresTransferExecutionRepository,
    )

    transfer_execution_handler = TransferMoneyHandler(
        PostgresTransferExecutionRepository(),
        db=material_db,
        resolver=PostgresTransferAccountResolver(),
    )
    transfer_dispatcher = TransferExecutionDispatcher(transfer_execution_handler)
    # Reversal (Finance Module Slice 7): same in-process capability-boundary
    # wiring as transfer above. The resolver re-verifies the target still
    # exists and hasn't already been reversed/voided at confirm time -- the
    # WhatsApp workflow already resolved "the most recent expense/transfer"
    # into a concrete id during seeding (runtime/inbound_journey.py), so this
    # is defense-in-depth, not name resolution.
    from mesiri.application.finance.reverse_dispatcher import ReverseExecutionDispatcher
    from mesiri.application.finance.reverse_handler import ReverseTransactionHandler
    from mesiri.application.finance.reverse_resolution import PostgresReverseTargetResolver
    from mesiri.infrastructure.postgres.repositories.reverse_execution import (
        PostgresReverseExecutionRepository,
    )

    reverse_execution_handler = ReverseTransactionHandler(
        PostgresReverseExecutionRepository(),
        db=material_db,
        resolver=PostgresReverseTargetResolver(),
    )
    reverse_dispatcher = ReverseExecutionDispatcher(reverse_execution_handler)
    # Routes a confirmed action to the dispatcher registered for its
    # action_type -- InteractionHandler only ever holds one ExecutionDispatcher.
    from interactions.execution_router import ActionTypeRoutingDispatcher

    # Labour attendance (Phase 5): same in-process capability-boundary wiring
    # as Materials above, reusing the same material_db transaction pool. No
    # resolver, unlike Materials -- worker matching already happened in the
    # workflow before confirmation (see application/labour/handlers.py).
    from mesiri.application.labour.dispatcher import LabourExecutionDispatcher
    from mesiri.application.labour.handlers import ExecuteConfirmedLabourAttendanceHandler
    from mesiri.infrastructure.postgres.repositories.labour_execution import (
        PostgresLabourExecutionRepository,
    )
    from mesiri_contracts.assistant.draft_action import DraftActionType

    labour_execution_handler = ExecuteConfirmedLabourAttendanceHandler(
        db=material_db,
        repo=PostgresLabourExecutionRepository(),
    )
    labour_dispatcher = LabourExecutionDispatcher(labour_execution_handler)

    # Activity creation (Daily Reporting, Phase 3): same in-process
    # capability-boundary wiring as Materials/Labour above, reusing the same
    # material_db transaction pool. The resolver re-verifies each stated
    # quantity's unit against units_of_measure at confirm time (defense-in-
    # depth, mirrors PostgresMaterialResolver) -- location/work-package
    # resolution is a separate gate (plan §1B.2) that hasn't been built yet,
    # so those fields simply stay null when unresolved (P4).
    from mesiri.application.progress.dispatcher import (
        AddProgressUpdateExecutionDispatcher,
        CloseSiteIssueExecutionDispatcher,
        CreateActivityExecutionDispatcher,
        ReportSiteIssueExecutionDispatcher,
    )
    from mesiri.application.progress.handlers import (
        ExecuteConfirmedAddProgressUpdateHandler,
        ExecuteConfirmedCloseSiteIssueHandler,
        ExecuteConfirmedCreateActivityHandler,
        ExecuteConfirmedReportSiteIssueHandler,
    )
    from mesiri.application.progress.resolution import PostgresProgressUnitResolver
    from mesiri.infrastructure.postgres.repositories.progress_execution import (
        PostgresProgressExecutionRepository,
    )

    progress_execution_repo = PostgresProgressExecutionRepository()
    progress_unit_resolver = PostgresProgressUnitResolver()
    create_activity_handler = ExecuteConfirmedCreateActivityHandler(
        db=material_db,
        repo=progress_execution_repo,
        resolver=progress_unit_resolver,
    )
    create_activity_dispatcher = CreateActivityExecutionDispatcher(create_activity_handler)
    # Activity Continuation (Daily Reporting): same repo/resolver as Activity
    # creation above -- both commands persist to the same tables via
    # PostgresProgressExecutionRepository, so there is exactly one instance
    # of each, shared by both handlers, same as Material's receipt/usage
    # commands share one dispatcher.
    add_progress_update_handler = ExecuteConfirmedAddProgressUpdateHandler(
        db=material_db,
        repo=progress_execution_repo,
        resolver=progress_unit_resolver,
    )
    add_progress_update_dispatcher = AddProgressUpdateExecutionDispatcher(
        add_progress_update_handler
    )
    # Site Issue Report: same repo as Activity creation/continuation above --
    # all three commands persist to tables PostgresProgressExecutionRepository
    # owns, so this is the same shared instance, not a new one. No resolver
    # (issue_type/severity are closed enums, nothing to resolve).
    report_site_issue_handler = ExecuteConfirmedReportSiteIssueHandler(
        db=material_db,
        repo=progress_execution_repo,
    )
    report_site_issue_dispatcher = ReportSiteIssueExecutionDispatcher(report_site_issue_handler)
    # Site Issue Close-out (acknowledge/resolve/wont_fix): same repo as the
    # three Progress handlers above -- no resolver here either (the
    # CURRENT-status re-check is inlined in persist_close_site_issue_success
    # itself, since it's a single self-contained row check, not a
    # cross-repository lookup like Reversal's).
    close_site_issue_handler = ExecuteConfirmedCloseSiteIssueHandler(
        db=material_db,
        repo=progress_execution_repo,
    )
    close_site_issue_dispatcher = CloseSiteIssueExecutionDispatcher(close_site_issue_handler)

    execution_dispatcher = ActionTypeRoutingDispatcher(
        {
            DraftActionType.RECORD_MATERIAL_RECEIPT: material_dispatcher,
            DraftActionType.RECORD_MATERIAL_USAGE: material_dispatcher,
            DraftActionType.RECORD_EXPENSE: expense_dispatcher,
            DraftActionType.MANAGE_MONEY_ACCOUNT: account_admin_dispatcher,
            DraftActionType.TRANSFER_MONEY: transfer_dispatcher,
            DraftActionType.REVERSE_TRANSACTION: reverse_dispatcher,
            DraftActionType.RECORD_LABOUR_ATTENDANCE: labour_dispatcher,
            DraftActionType.CREATE_ACTIVITY: create_activity_dispatcher,
            DraftActionType.ADD_PROGRESS_UPDATE: add_progress_update_dispatcher,
            DraftActionType.RECORD_SITE_ISSUE: report_site_issue_dispatcher,
            DraftActionType.CLOSE_SITE_ISSUE: close_site_issue_dispatcher,
        }
    )
    # Read-only inventory lookups for the material.inventory_query workflow --
    # reuses the same material_db connection pool, never opens a write
    # transaction. See runtime/inventory_query.py.
    from runtime.inventory_query import MaterialInventoryQueryService

    inventory_query = MaterialInventoryQueryService(material_db)
    # Read-only catalog/units-of-measure lookups for the material/unit
    # resolution gate -- same reasoning and same material_db as
    # inventory_query above. See runtime/material_catalog_query.py.
    from runtime.material_catalog_query import MaterialCatalogQueryService

    catalog_query = MaterialCatalogQueryService(material_db)
    # Per-org settings (which roles may add a material from WhatsApp, etc) --
    # same reasoning and same material_db as catalog_query above. See
    # runtime/org_settings_query.py.
    from runtime.org_settings_query import OrganizationSettingsQueryService

    org_settings_query = OrganizationSettingsQueryService(material_db)
    # Read-only expense category names, fed into the extraction call so the
    # AI can pick from the org's real categories -- same reasoning and same
    # material_db as catalog_query above. See runtime/expense_category_query.py.
    from runtime.expense_category_query import ExpenseCategoryQueryService

    expense_category_query = ExpenseCategoryQueryService(material_db, redis=redis_client)
    # Read-only money-account lookups + lazy default-account bootstrap, fed
    # into expense_capture's "which account?" slot (Finance Module Slice 1)
    # -- same reasoning and same material_db as catalog_query above. See
    # runtime/money_account_query.py.
    from runtime.money_account_query import MoneyAccountQueryService

    money_account_query = MoneyAccountQueryService(material_db)
    # Resolves a petty cash recipient's name into their employee-advance
    # account (auto-created on first issuance), fed into the petty-cash
    # workflow's "other account" slot (Finance Module Slice 5) -- same
    # reasoning and same material_db as catalog_query above. See
    # runtime/petty_cash_query.py.
    from runtime.petty_cash_query import PettyCashRecipientQueryService

    petty_cash_query = PettyCashRecipientQueryService(material_db)
    # Resolves "the most recent expense/transfer" for the reverse workflow's
    # target (Finance Module Slice 7) -- same reasoning and same material_db
    # as catalog_query above. See runtime/reversal_query.py.
    from runtime.reversal_query import ReversalTargetQueryService

    reversal_query = ReversalTargetQueryService(material_db)
    # Resolves "my last reported issue" for the site_issue_close workflow's
    # target -- same reasoning and same material_db as reversal_query above.
    # See runtime/site_issue_query.py.
    from runtime.site_issue_query import SiteIssueTargetQueryService

    site_issue_query = SiteIssueTargetQueryService(material_db)
    # Flags a likely-duplicate expense before expense_capture's graph runs
    # (Finance Module Slice 8) -- same reasoning and same material_db as
    # catalog_query above. See runtime/duplicate_expense_query.py.
    from runtime.duplicate_expense_query import DuplicateExpenseQueryService

    duplicate_expense_query = DuplicateExpenseQueryService(material_db)
    # Workforce register reads for the Labour attendance workflow. Now the
    # real reader (2026-07-27): workforce_workers exists, has dashboard CRUD,
    # and labour_attendance_lines gives genuine "worked here before" signals.
    # Until this line changed, a worker added on the dashboard was invisible
    # to WhatsApp matching -- the register was real but nothing read it.
    from runtime.workforce_query import PostgresWorkforceQueryService

    workforce_query = PostgresWorkforceQueryService(material_db)
    # Open-activity lookup for the Activity Continuation workflow (Daily
    # Reporting) -- resolves which Activity "finished plastering" continues,
    # before the graph runs. Reuses the same pool; never opens a write
    # transaction. See runtime/activity_query.py.
    from runtime.activity_query import ActivityQueryService

    activity_query = ActivityQueryService(material_db)
    # Direct evidence attach for #2 Batch Media's "Site Update" photo
    # purpose -- never a workflow (see AttachEvidenceCommand's docstring).
    # Reuses the same pool; opens its own write transaction only when
    # attach_photos is actually called. See runtime/evidence_query.py.
    from runtime.evidence_query import EvidenceAttachService

    evidence_query = EvidenceAttachService(material_db)
    # #10 Human Review: creates a durable escalation record the moment #7
    # Low-Confidence Routing decides ESCALATE (nothing usable extracted at
    # all). See runtime/escalation_query.py.
    from runtime.escalation_query import EscalationCreateService

    escalation_query = EscalationCreateService(material_db)
    # #1 Multi-Activity / #13 Cross-Module Trigger: queues segments AFTER
    # the first in a multi-segment message, started one at a time as each
    # prior segment's confirmation resolves. See workflows/batch_store.py
    # and workflows/batch.py.
    from workflows.batch_store import PendingBatchStore

    batch_store = PendingBatchStore(redis_client)
    # #25 AI Follow-up: remembers which Activity a proactive "want to
    # attach a completion photo?" offer was about, so the next photo skips
    # the normal purpose picker. See interactions/completion_photo_hint.py.
    from interactions.completion_photo_hint import CompletionPhotoHintStore

    completion_photo_hint_store = CompletionPhotoHintStore(redis_client)
    # M19 conversation memory -- current project/site (existing
    # RedisActiveContextStore), current activity/date (new), and a capped
    # recent-turns history, composed behind one loader/coordinator pair. See
    # memory/requirements.py for the full scope list and why each is a HINT,
    # never authoritative. Requires workflow_runtime (built below) for its
    # pending-confirmation check, so this line must stay after that build.
    from memory import build_conversation_memory

    memory_loader, memory_coordinator = build_conversation_memory(redis_client, workflow_runtime)
    # Read-only attendance lookups for the labour.query workflow ("how many
    # workers today?"). Reuses the same pool; never opens a write
    # transaction. See runtime/labour_query_service.py.
    from runtime.labour_query_service import LabourQueryService

    labour_query_service = LabourQueryService(material_db)
    # Read-only progress/activity + open-issue lookups for the activity.query
    # workflow (#17 Search / Ask Mesiri -- "what did I log today?"). Reuses
    # the same pool; never opens a write transaction. See
    # runtime/activity_search_service.py.
    from runtime.activity_search_service import ActivitySearchService

    activity_search_service = ActivitySearchService(material_db)
    # Status lookup for the dpr.request workflow ("send me today's DPR" --
    # #16 Daily Report Generation). Reuses the same pool; never opens a
    # write transaction. See runtime/dpr_request_query.py.
    from runtime.dpr_request_query import DprRequestQueryService

    dpr_request_query = DprRequestQueryService(material_db)
    # Flags a vendor name that doesn't match any existing active vendor, fed
    # into expense_capture's "create this vendor?" slot -- same reasoning and
    # same material_db as catalog_query above. See runtime/vendor_query.py.
    from runtime.vendor_query import VendorQueryService

    vendor_query = VendorQueryService(material_db)
    # Read-only expense list/sum lookups for the expense-query workflow
    # (Finance Module Slice 2) -- same reasoning and same material_db as
    # money_account_query above. See runtime/expense_query_service.py.
    from runtime.expense_query_service import ExpenseQueryService

    expense_query_service = ExpenseQueryService(material_db)
    # Slow-path interaction classifier: while a confirmation is pending, a
    # message that isn't a plain "yes"/"no" (e.g. "40 bags of cement" instead
    # of the drafted 50) needs an LLM to recognize it as a CORRECTION rather
    # than a brand-new report. Without this wired, interactions/handler.py's
    # handle_slow_path() short-circuits to None (classifier is None) and every
    # such message falls through to the single-active-invariant block, which
    # just re-shows the stale draft untouched -- this was a real bug, not a
    # missing feature: the classifier existed but was never constructed here.
    from interactions.llm_classifier import AdapterInteractionClassifier
    from mesiri_ai.resolver import DynamicAIProviderResolver

    # Built here (rather than at its previous spot, after this classifier)
    # so llm_classifier's generate_json calls stop being the one path with
    # zero journey_traces rows -- traced report showed interactive-tap
    # messages hitting 32s wall-clock with nothing logged anywhere; this was
    # a hidden 1-2 sequential-LLM-call chain (segmenter, then an extractor
    # per CORRECTION segment), not DB/API latency as first suspected.
    trace_logger: TraceLogger = PostgresTraceLogger()

    interaction_classifier = AdapterInteractionClassifier(
        DynamicAIProviderResolver(material_db, redis_client, _backend_settings),
        trace_logger=trace_logger,
    )
    # Post-confirmation receipt image (see AGENTS.md's Module Placement Log
    # and channel/receipt/). One long-lived headless-Chromium instance for
    # the whole process -- ReceiptRenderer launches it lazily on first
    # render, not here, so container construction never needs a browser
    # installed. Closed in runtime/lifecycle.py's shutdown handler.
    from channel.receipt import ReceiptRenderer, RecordReceiptBuilder

    receipt_renderer = ReceiptRenderer()
    record_receipt_builder = RecordReceiptBuilder(receipt_renderer)
    # M7: resolves a confirmation reply into the pending workflow, or None
    # (fall through to the normal understanding journey). M8: when a CONFIRM
    # resolves to CONFIRMED, the dispatcher executes the domain write
    # synchronously in the same request and the reply reflects the real outcome.
    interaction_handler = build_interaction_handler(
        workflow_runtime,
        classifier=interaction_classifier,
        dispatcher=execution_dispatcher,
        receipt_builder=record_receipt_builder,
        memory_coordinator=memory_coordinator,
        planner=planner,
        batch_store=batch_store,
        completion_photo_hint_store=completion_photo_hint_store,
    )
    sender = WhatsAppSender(
        client=http_client,
        access_token=settings.access_token,
        phone_number_id=settings.phone_number_id,
        api_version=settings.api_version,
        graph_base_url=settings.graph_base_url,
    )

    # Backend capability boundary: create once, reuse the connection pool.
    # message_logger/trace_logger build their engine lazily on first use (see
    # their _get_engine()) so importing/constructing the container never
    # requires a live DB driver import — building it eagerly here broke that
    # and made container construction fail wherever asyncpg couldn't import.
    actor_reader = PostgresActorReader()
    message_logger: MessageLogger = PostgresMessageLogger()

    # _send_understanding_reply (the old reply_sender=... callback) is gone:
    # inbound_journey._render_reply() now covers every outcome, so the
    # understanding-only fallback it fed was dead weight.
    async def _on_normalized(message, raw_payload, retry_of_id=None) -> None:  # type: ignore[no-untyped-def]
        """Never let an unhandled exception reach the user as silence.

        The journey below has error handling at every stage it anticipates,
        but anything it does *not* anticipate propagates to
        WhatsAppReceiver._process_message, which logs it and writes a trace
        row -- and sends nothing. From the sender's side that is
        indistinguishable from Mesiri being down: they photographed an
        attendance sheet, answered "what is this photo for?", and then
        nothing ever came back.

        inbound_journey._render_reply already states the principle for the
        paths it owns ("a message that reaches the assistant and gets no
        answer is indistinguishable from Mesiri being down"); this extends
        the same guarantee to the paths nobody predicted. The exception is
        still re-raised so the trace row and the log line are unchanged --
        this only adds the reply that was missing.
        """
        try:
            await _run_journey(message, raw_payload, retry_of_id)
        except Exception:
            _log.exception(
                "inbound.unhandled correlation_id=%s message_id=%s",
                getattr(message, "correlation_id", "?"),
                getattr(message, "message_id", "?"),
            )
            try:
                await sender.send_text(
                    message.sender.wa_id,
                    "⚠️ Something went wrong handling that — nothing was recorded. "
                    "Please try again, and tell us if it keeps happening.",
                )
            except Exception:  # noqa: BLE001 -- the send itself can fail; the
                # re-raise below still gets the failure into the trace log.
                _log.exception("inbound.unhandled_reply_failed")
            raise

    async def _mark_read_on_claim(message_id: str) -> None:
        """Blue tick + "typing..." -- wired into WhatsAppReceiver as
        on_message_claimed so it fires the instant the webhook lands, in
        parallel with processing. It used to run here at the top of
        _run_journey, which for voice/image meant the sender saw no blue
        tick until the Meta media download (~1.5-1.7s measured), upload and
        normalization had all finished first."""
        await sender.mark_as_read(message_id)

    # Held so a fire-and-forget ack task can't be garbage-collected mid-flight
    # -- asyncio only keeps a weak reference to a task nothing else holds.
    # Same reasoning, same pattern as WhatsAppReceiver._background_tasks.
    _ack_tasks: set[asyncio.Task[None]] = set()

    def _fire_processing_ack(wa_id: str, modality: InputModality) -> None:
        """Schedule _send_processing_ack without awaiting it -- the caller's
        real work (the slow understanding call that follows) must start
        immediately, not after this ~600-900ms Meta round trip."""
        task = asyncio.create_task(_send_processing_ack(wa_id, modality))
        _ack_tasks.add(task)
        task.add_done_callback(_ack_tasks.discard)

    async def _send_processing_ack(wa_id: str, modality: InputModality) -> None:
        """A second, real message sent before understanding starts, not just
        the read-receipt blue tick.

        Voice/image replies still take several real seconds (traced:
        analyze_image ~6.4s, understand_voice ~3.2s, plus a confirmed
        expense's receipt render + a second send) -- without this the
        sender watches "typing..." with zero information for that whole
        window, which reads as "did this even go through?" rather than
        "still working on it". Fire-and-forget like the read receipt:
        nothing downstream depends on it, and a failure here must never
        delay or replace the real reply.

        Deliberately skips text/interactive -- those already reply in
        under ~2s (measured), where a second message would arrive at
        almost the same time as the real one and just add noise.
        """
        text = _PROCESSING_ACK_TEXT.get(modality)
        if text is None:
            return
        try:
            await sender.send_text(wa_id, text)
        except Exception:  # noqa: BLE001
            _log.exception(
                "processing_ack_failed wa_id=%s modality=%s", wa_id, modality.value
            )

    async def _run_journey(message, raw_payload, retry_of_id=None) -> None:  # type: ignore[no-untyped-def]
        timer = StepTimer()
        try:
            await _run_journey_steps(message, raw_payload, retry_of_id, timer)
        finally:
            # Emitted in `finally` so every path is covered by one write --
            # this block has a dozen early returns (unregistered sender,
            # suspended org, a fast path that handled the message outright),
            # and a per-return emit would be a dozen chances to miss one.
            # duration_ms is the whole journey; subtract the
            # process_inbound_message lap for the pre-pipeline cost alone.
            try:
                await trace_logger.log_stage(
                    correlation_id=message.correlation_id,
                    stage="prepipeline",
                    stage_payload=timer.steps,
                    duration_ms=timer.total_ms,
                    succeeded=True,
                )
            except Exception:  # noqa: BLE001 -- diagnostics must never break a message
                _log.exception("prepipeline.trace_failed correlation_id=%s", message.correlation_id)

    async def _run_journey_steps(message, raw_payload, retry_of_id, timer) -> None:  # type: ignore[no-untyped-def]
        wa_id = message.sender.wa_id

        # M4: resolve the sender before spending on understanding.
        try:
            ctx = await resolve_sender(actor_reader, wa_id)
        except Exception:  # noqa: BLE001 — never let a lookup error drop the message silently
            _log.exception("context.identity_lookup_failed wa_id=%s", wa_id)
            ctx = None

        timer.lap("resolve_sender")
        org_id = ctx.organization_id if ctx else None

        # Best-effort inbound message log (for debugging/replay). raw_payload
        # is a self-contained, replayable envelope of the raw Meta webhook
        # JSON (see ingress.receiver.WhatsAppReceiver._envelope) -- stored in
        # full so a failed message can later be replayed via the admin retry
        # action. A retry reuses the same WhatsApp message_id, so its dedup_key
        # is suffixed with the new correlation_id to avoid colliding with the
        # original row (ON CONFLICT (dedup_key) DO NOTHING would otherwise
        # silently drop the retry attempt).
        #
        # Phase 7 perf: fired in the background with ensure_future so the DB
        # write does not block the reply path. The return value is never read
        # and the write is already best-effort (it was wrapped in try/except
        # at the call site before this change). Same pattern as _safe() used
        # throughout this module. In the rare event of a process crash within
        # ~50ms, this one audit row is lost; the message itself is not lost
        # because WhatsApp retries unacknowledged webhooks.
        dedup_key = (
            message.message_id
            if retry_of_id is None
            else f"{message.message_id}:retry:{message.correlation_id}"
        )
        asyncio.ensure_future(
            message_logger.log_received(
                correlation_id=message.correlation_id,
                sender_wa_id=wa_id,
                message_type=message.modality.value,
                raw_payload=dict(raw_payload),
                normalized_message=message.model_dump(mode="json"),
                body_text=message.text,
                media_object_key=message.media.object_key if message.media else None,
                dedup_key=dedup_key,
                retry_of_id=retry_of_id,
                organization_id=org_id,
            )
        )
        timer.lap("log_received")

        if ctx is None:
            _log.info("context.sender_unregistered wa_id=%s", wa_id)
            await sender.send_text(wa_id, UNREGISTERED_MESSAGE)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=UNREGISTERED_MESSAGE
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        if ctx.organization_id is None:
            _log.info("context.user_no_org user=%s", ctx.user_id)
            reply = NO_ORG_MESSAGE.format(name=ctx.full_name)
            await sender.send_text(wa_id, reply)
            await message_logger.log_reply(correlation_id=message.correlation_id, reply=reply)
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        if not ctx.org_active:
            _log.info("context.org_suspended org=%s", ctx.organization_id)
            await sender.send_text(wa_id, ORG_SUSPENDED_MESSAGE)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=ORG_SUSPENDED_MESSAGE
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        _log.info(
            "context.resolved user=%s org=%s projects=%s",
            ctx.user_id,
            ctx.organization_id,
            len(ctx.projects),
        )

        # A message type Mesiri can't act on yet (PDF, video, sticker,
        # location pin, shared contact, music file). Answered here rather
        # than dropped: normalization used to raise on these, aborting
        # ingress with no reply at all, so the sender couldn't tell "Mesiri
        # can't read PDFs" from "Mesiri is down" and had no idea whether
        # their report had landed.
        #
        # Placed after the identity/org gates on purpose -- an unregistered
        # sender or a suspended org needs to hear *that* first, since it's
        # the more actionable problem. Placed before the interaction fast
        # path because an UNKNOWN-modality message can never be a
        # confirmation reply or a menu tap, and must not be able to resolve
        # a pending draft.
        if message.modality is InputModality.UNKNOWN:
            raw_type = (message.metadata or {}).get("raw_type")
            if str(raw_type or "") in SILENTLY_IGNORED_RAW_TYPES:
                # An emoji reaction on one of our own replies, or a Meta
                # system notice -- logged, but replying would be noise.
                _log.info("ingress.ignored_raw_type type=%s user=%s", raw_type, ctx.user_id)
                await message_logger.mark_completed(correlation_id=message.correlation_id)
                return
            _log.info("ingress.unsupported_raw_type type=%s user=%s", raw_type, ctx.user_id)
            unsupported_reply = render_unsupported_media_reply(raw_type)
            await sender.send_text(wa_id, unsupported_reply)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=unsupported_reply
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # M7: if the user has a workflow awaiting confirmation and this message
        # is a confirmation reply, resume it and stop — the AI pipeline (and its
        # token cost) is never touched. A plain "yes" ends here.
        try:
            handled = await interaction_handler.handle_fast_path(ctx.user_id, message, actor=ctx)
            timer.lap("handle_fast_path")
        except Exception:  # noqa: BLE001 — a resume error must not drop the message
            _log.exception("interaction.handle_failed user=%s", ctx.user_id)
            handled = None
        if handled is not None:
            # Phase 4: send confirmation text FIRST so the user sees it
            # immediately, then await the receipt PNG (Playwright render) and
            # send the image. This keeps the reply feeling instant even when
            # the page-pool is cold.
            await sender.send_text(wa_id, handled.reply_text)
            if handled.receipt_coro is not None:
                try:
                    image_bytes = await handled.receipt_coro
                except Exception:  # noqa: BLE001 -- receipt failure must never drop the message
                    image_bytes = None
                if image_bytes is not None:
                    sent = await sender.send_image(wa_id, image_bytes, caption=None)
                    if not sent:
                        pass  # image already tried; text was already sent above
            # Worker promotion follow-up. This belongs *here*, not in
            # inbound_journey: a confirmation reply is resolved by the fast
            # path above and returns before the journey ever runs, so a hook
            # placed there never fires for the one event it exists to follow
            # -- which is exactly why no promotion offer was ever sent.
            # Attendance text and receipt are already delivered above; this is
            # strictly a second-step offer that never delays either.
            from runtime.inbound_journey import _maybe_trigger_worker_promotion

            try:
                await _maybe_trigger_worker_promotion(
                    handled,
                    workflow_runtime,
                    workforce_query,
                    ctx,
                    wa_id,
                    sender.send_text,
                )
            except Exception:  # noqa: BLE001 — promotion never disturbs saved attendance
                _log.exception("worker_promotion.trigger_failed user=%s", ctx.user_id)
            # Phase 8 perf: user reply is already sent above. These 4 writes
            # are order-independent audit rows -- run them concurrently.
            await asyncio.gather(
                message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=handled.reply_text
                ),
                message_logger.link_workflow_instance(
                    correlation_id=message.correlation_id,
                    workflow_instance_id=handled.result.workflow_instance_id,
                ) if handled.result.workflow_instance_id else asyncio.sleep(0),
                message_logger.update_context(
                    correlation_id=message.correlation_id,
                    project_id=handled.project_id,
                    site_id=handled.site_id,
                ),
                message_logger.mark_completed(correlation_id=message.correlation_id),
                return_exceptions=True,
            )
            return

        # Finance Module Slice 1: if the user has a workflow awaiting a slot
        # answer (e.g. "which account?") and this message can answer it
        # (text/interactive only -- see handle_slot_answer's docstring),
        # resume it and stop, same principle and same priority as the
        # confirmation fast path above.
        try:
            slot_handled = await interaction_handler.handle_slot_answer(ctx.user_id, message)
            timer.lap("handle_slot_answer")
        except Exception:  # noqa: BLE001 — a resume error must not drop the message
            _log.exception("interaction.slot_answer_failed user=%s", ctx.user_id)
            slot_handled = None
        if slot_handled is not None:
            # Resuming a slot answer can land on any WorkflowRunResult status
            # -- another AWAITING_INPUT (next slot) or STARTED (draft ready,
            # needs Yes/No) just as often as COMPLETED -- so this must render
            # through the same status-aware ReplySpec logic every other
            # workflow-run reply uses, not always plain text. See
            # runtime/inbound_journey.py's render_workflow_run_reply_spec
            # docstring for the bug this fixes.
            from runtime.inbound_journey import render_workflow_run_reply_spec

            reply = render_workflow_run_reply_spec(slot_handled.result)
            await send_reply_spec(
                reply,
                wa_id,
                send_text=sender.send_text,
                send_list=sender.send_list,
                send_button=sender.send_button,
            )
            # The other half of worker promotion: answering the offer arrives
            # here, as a slot answer. The node decided who to add but cannot
            # write (it is pure), so the inserts happen on this side. Same
            # reason as the fast path above -- inbound_journey never runs for
            # a slot answer either.
            from runtime.inbound_journey import _create_promoted_workers

            try:
                await _create_promoted_workers(
                    slot_handled.result,
                    workforce_query,
                    ctx,
                    wa_id,
                    sender.send_text,
                )
            except Exception:  # noqa: BLE001 — never disturbs saved attendance
                _log.exception("worker_promotion.create_failed user=%s", ctx.user_id)
            await asyncio.gather(
                message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=reply.text
                ),
                message_logger.link_workflow_instance(
                    correlation_id=message.correlation_id,
                    workflow_instance_id=slot_handled.result.workflow_instance_id,
                ) if slot_handled.result.workflow_instance_id else asyncio.sleep(0),
                message_logger.update_context(
                    correlation_id=message.correlation_id,
                    project_id=slot_handled.project_id,
                    site_id=slot_handled.site_id,
                ),
                message_logger.mark_completed(correlation_id=message.correlation_id),
                return_exceptions=True,
            )
            return

        # Deterministic "create/rename/deactivate account" command (Finance
        # Module Slice 6, account-admin scope) -- bypasses the AI pipeline
        # entirely, same priority as the slot-answer/confirmation fast paths
        # above. See runtime/account_admin_journey.py.
        try:
            account_admin_handled = await try_handle_account_admin_command(
                message, ctx, workflow_runtime
            )
            timer.lap("account_admin_command")
        except Exception:  # noqa: BLE001 — a resume error must not drop the message
            _log.exception("account_admin.command_failed user=%s", ctx.user_id)
            account_admin_handled = None
        if account_admin_handled is not None:
            await sender.send_text(wa_id, account_admin_handled.reply_text)
            run = account_admin_handled.workflow_run
            await asyncio.gather(
                message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=account_admin_handled.reply_text
                ),
                message_logger.link_workflow_instance(
                    correlation_id=message.correlation_id,
                    workflow_instance_id=run.workflow_instance_id,
                ) if (run is not None and run.workflow_instance_id) else asyncio.sleep(0),
                message_logger.mark_completed(correlation_id=message.correlation_id),
                return_exceptions=True,
            )
            return

        # Category-menu tap (from render_direct_reply's greeting list): a
        # deterministic reply, no AI call, no workflow state touched. Runs
        # after the confirmation fast path so a pending confirmation still
        # wins over a stale menu tap from an earlier message. See
        # InteractionHandler.handle_category_tap for why this lives there.
        category_prompt = interaction_handler.handle_category_tap(message)
        if category_prompt is not None:
            row_id = message.metadata.get("interactive_reply_id")
            hint = CATEGORY_SEMANTIC_HINT.get(row_id) if row_id else None
            if hint:
                try:
                    await category_hint_store.set_hint(user_id=ctx.user_id, semantic_hint=hint)
                except Exception:  # noqa: BLE001 — a hint is a nudge, never worth losing the reply
                    _log.exception("category_hint.set_failed user=%s", ctx.user_id)
            await send_reply_spec(
                category_prompt,
                wa_id,
                send_text=sender.send_text,
                send_list=sender.send_list,
                send_button=sender.send_button,
            )
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=category_prompt.text
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # Material Arrived/Used button tap (from render_category_prompt's
        # "cat_material" case) -- locks direction as a fallback default for
        # canonicalization (see build_canonical_event's direction_hint), never
        # an override of what the report itself says. Deterministic, no AI,
        # same principle as the category tap above.
        material_direction_prompt = interaction_handler.handle_material_direction_tap(message)
        if material_direction_prompt is not None:
            row_id = message.metadata.get("interactive_reply_id")
            direction = "received" if row_id == "dir_received" else "used"
            try:
                await category_hint_store.set_hint(
                    user_id=ctx.user_id, semantic_hint="material_update", direction=direction
                )
            except Exception:  # noqa: BLE001 — a hint is a nudge, never worth losing the reply
                _log.exception("category_hint.set_failed user=%s", ctx.user_id)
            await sender.send_text(wa_id, material_direction_prompt)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=material_direction_prompt
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # A tap on the "what is this photo for?" list (see
        # interactions/image_purpose.py and channel/replies.IMAGE_PURPOSE_ROWS)
        # -- resumes the whole HELD BATCH (not this tap message) with the
        # chosen purpose. Deterministic tap detection, same principle as the
        # two fast paths above. #2 Batch Media: the batch can hold more than
        # one photo (a burst); "img_site_update" attaches ALL of them to the
        # open activity in one write, while "img_expense"/"img_attendance"
        # still only process the FIRST through the normal single-report
        # confirm flow (see render_batch_overflow_reply's docstring for why).
        image_purpose_row_id = interaction_handler.handle_image_purpose_tap(message)
        if image_purpose_row_id is not None:
            from channel.replies import (
                IMAGE_PURPOSE_SEMANTIC_HINT,
                render_batch_overflow_reply,
                render_evidence_attached_reply,
                render_no_open_activity_for_evidence_reply,
            )

            held_batch = await pending_media_store.pop_batch(user_id=ctx.user_id)
            timer.lap("pop_pending_media")
            if not held_batch:
                expired_reply = "That photo has expired — please resend it."
                await sender.send_text(wa_id, expired_reply)
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=expired_reply
                )
                await message_logger.mark_completed(correlation_id=message.correlation_id)
                return

            if image_purpose_row_id == "img_site_update":
                # Evidence attach is a direct write, never a confirmable
                # workflow (see AttachEvidenceCommand's docstring) -- no
                # single-active-invariant concern, so the WHOLE batch
                # attaches in one shot regardless of size.
                found = await activity_query.find_open_activity(
                    organization_id=ctx.organization_id,
                    site_id=None,
                    reported_by_user_id=ctx.user_id,
                )
                if found is None:
                    reply_text = render_no_open_activity_for_evidence_reply()
                else:
                    media_keys = [m.media.object_key for m in held_batch if m.media is not None]
                    created_ids = await evidence_query.attach_photos(
                        organization_id=ctx.organization_id,
                        activity_id=found["activity_id"],
                        media_object_keys=media_keys,
                        uploaded_by=ctx.user_id,
                        correlation_id=message.correlation_id,
                    )
                    summary_bits = [
                        b for b in (found.get("work_type"), found.get("narrative")) if b
                    ]
                    activity_summary = " — ".join(summary_bits) if summary_bits else None
                    reply_text = render_evidence_attached_reply(
                        count=len(created_ids), activity_summary=activity_summary
                    )
                await sender.send_text(wa_id, reply_text)
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=reply_text
                )
                await message_logger.mark_completed(correlation_id=message.correlation_id)
                return

            held_message = held_batch[0]
            _fire_processing_ack(wa_id, held_message.modality)
            await process_inbound_message(
                held_message,
                actor_user_id=ctx.user_id,
                actor=ctx,
                semantic_hint=IMAGE_PURPOSE_SEMANTIC_HINT[image_purpose_row_id],
                category_hint_store=category_hint_store,
                pipeline=pipeline,
                context_resolver=context_resolver,
                planner=planner,
                workflow_runtime=workflow_runtime,
                interaction_handler=interaction_handler,
                send_text=sender.send_text_capturing_id,
                send_list=sender.send_list,
                send_button=sender.send_button,
                send_image=sender.send_image,
                send_document=sender.send_document,
                object_storage=object_storage,
                context_debug=settings.context_debug,
                message_logger=message_logger,
                trace_logger=trace_logger,
                inventory_query=inventory_query,
                catalog_query=catalog_query,
                org_settings_query=org_settings_query,
                expense_category_query=expense_category_query,
                money_account_query=money_account_query,
                petty_cash_query=petty_cash_query,
                reversal_query=reversal_query,
                site_issue_query=site_issue_query,
                duplicate_expense_query=duplicate_expense_query,
                workforce_query=workforce_query,
                activity_query=activity_query,
                labour_query_service=labour_query_service,
                activity_search_service=activity_search_service,
                dpr_request_query=dpr_request_query,
                vendor_query=vendor_query,
                expense_query_service=expense_query_service,
                pending_report_store=pending_report_store,
                memory_loader=memory_loader,
                memory_coordinator=memory_coordinator,
                batch_store=batch_store,
                escalation_query=escalation_query,
            )
            timer.lap("process_inbound_message_held_media")
            if len(held_batch) > 1:
                overflow_reply = render_batch_overflow_reply(
                    held_count=len(held_batch), remaining_count=len(held_batch) - 1
                )
                await sender.send_text(wa_id, overflow_reply)
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=overflow_reply
                )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # Bare "hi"/"menu"/"help"/etc (see greeting_phrases.json): the AI
        # pipeline is never touched, same principle as the two fast paths
        # above. Text only -- voice can't be checked until Sarvam
        # transcribes it, so the identical check runs again inside
        # understanding/pipeline.py post-transcription instead.
        greeting_reply = interaction_handler.handle_greeting_trigger(message)
        if greeting_reply is not None:
            if greeting_reply.list_rows:
                await sender.send_list(
                    wa_id,
                    body=greeting_reply.text,
                    button_label=greeting_reply.list_button_label or "Choose one",
                    rows=list(greeting_reply.list_rows),
                )
            else:
                await sender.send_text(wa_id, greeting_reply.text)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=greeting_reply.text
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # Bare "who am i"/"whoami"/"my profile"/etc (see
        # workflows/who_am_i/phrases.json): deterministic identity-lookup
        # fast path, same principle as the greeting trigger above -- the AI
        # pipeline is never touched. Uses ctx (already resolved above), so
        # no extra DB round-trip.
        whoami_reply_text = interaction_handler.handle_whoami_trigger(message, ctx)
        if whoami_reply_text is not None:
            await sender.send_text(wa_id, whoami_reply_text)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=whoami_reply_text
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        # Phase 6 perf: all of the resume_pending_report_with_* checks below can
        # only ever return something when the incoming message is a button/list tap
        # (InputModality.INTERACTIVE). For text and voice messages they always
        # return None, so we skip them entirely — eliminating up to 8 sequential
        # DB reads (pending_report_store lookups) from every normal message.
        if message.modality is InputModality.INTERACTIVE:
            # A tap on the material picker sent by the material-resolution gate
            # (runtime/inbound_journey.py, ambiguous/unmatched material name) --
            # resumes with material_id filled in and re-runs the remaining gates
            # (unit, then project) rather than assuming those are settled.
            material_reply = await resume_pending_report_with_material(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                catalog_query=catalog_query,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_material")
            if material_reply is not None:
                await send_reply_spec(
                    material_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=material_reply.text
                )
                return

            # A Yes/No tap on the "add this material to the catalog?" offer sent
            # when a reported name matched nothing and the sender's role is
            # allowed to create one (STA-139). Checked before the Stock Unit
            # mismatch resume below -- distinct row-id prefixes, but these two
            # answer different questions and must stay separately dispatched.
            material_create_reply = await resume_pending_report_with_material_create(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                catalog_query=catalog_query,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_material_create")
            if material_create_reply is not None:
                await send_reply_spec(
                    material_create_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=material_create_reply.text
                )
                return

            # A tap on the unit picker shown when a brand-new material's Stock
            # Unit couldn't be inferred from the report's own words -- creates
            # the catalog entry and continues the held report.
            material_unit_reply = await resume_pending_report_with_material_unit_choice(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                catalog_query=catalog_query,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_material_unit_choice")
            if material_unit_reply is not None:
                await send_reply_spec(
                    material_unit_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=material_unit_reply.text
                )
                return

            # A Yes/No tap on the Stock Unit mismatch clarification -- resumes
            # with unit_id filled in (or tells the sender to resend on "No") and
            # re-runs the project gate before planner/workflow.
            unit_reply = await resume_pending_report_with_unit(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                catalog_query=catalog_query,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_unit")
            if unit_reply is not None:
                await send_reply_spec(
                    unit_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=unit_reply.text
                )
                return

            # A tap on one of the three buttons sent by the stock sufficiency
            # gate (runtime/inbound_journey.py, usage quantity greater than what's
            # in stock) -- resumes with the report capped/switched-to-arrival/
            # cancelled per the tap, same principle as the other interactive fast
            # paths above.
            stock_reply = await resume_pending_report_with_stock_choice(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                planner=planner,
                workflow_runtime=workflow_runtime,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_stock_choice")
            if stock_reply is not None:
                await send_reply_spec(
                    stock_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=stock_reply.text
                )
                return

            # A tap on the project-picker list sent by the project-selection gate
            # (runtime/inbound_journey.py, when a report was otherwise complete
            # but no project could be resolved) -- resumes the held report with
            # the chosen project_id and runs planner/workflow directly, same
            # principle as the other interactive fast paths above.
            project_reply = await resume_pending_report_with_project(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_project")
            if project_reply is not None:
                await send_reply_spec(
                    project_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=project_reply.text
                )
                return

            # A tap on the site-picker list sent by the site-selection gate
            # (runtime/inbound_journey.py, once project is settled but the
            # project has more than one site) -- resumes the held report/query
            # with the chosen site_id (or None for "All Sites Combined") and
            # runs planner/workflow directly, same principle as the other
            # interactive fast paths above.
            site_reply = await resume_pending_report_with_site(
                message,
                ctx.user_id,
                pending_report_store=pending_report_store,
                planner=planner,
                workflow_runtime=workflow_runtime,
                actor=ctx,
                inventory_query=inventory_query,
                message_logger=message_logger,
            )
            timer.lap("resume_site")
            if site_reply is not None:
                await send_reply_spec(
                    site_reply,
                    wa_id,
                    send_text=sender.send_text,
                    send_list=sender.send_list,
                    send_button=sender.send_button,
                )
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=site_reply.text
                )
                return


        # #25 AI Follow-up: if Mesiri just asked "want to attach a
        # completion photo?" (interactions/handler.py, after an Activity is
        # marked COMPLETED), the very next photo answers that question --
        # skip the normal "what is this for?" picker entirely and attach
        # directly. Checked BEFORE the picker gate below on purpose: this
        # hint is pop-once and must not be silently skipped past for an
        # unrelated later photo.
        if message.modality is InputModality.IMAGE and message.media is not None:
            completion_activity_id = await completion_photo_hint_store.pop_hint(
                user_id=ctx.user_id
            )
            if completion_activity_id is not None:
                from channel.replies import render_evidence_attached_reply

                created_ids = await evidence_query.attach_photos(
                    organization_id=ctx.organization_id,
                    activity_id=completion_activity_id,
                    media_object_keys=[message.media.object_key],
                    uploaded_by=ctx.user_id,
                    correlation_id=message.correlation_id,
                )
                reply_text = render_evidence_attached_reply(
                    count=len(created_ids), activity_summary=None
                )
                await sender.send_text(wa_id, reply_text)
                await message_logger.log_reply(
                    correlation_id=message.correlation_id, reply=reply_text
                )
                await message_logger.mark_completed(correlation_id=message.correlation_id)
                return

        # A genuinely new image (not a tap answering the picker above) is
        # held while we ask "what is this photo for?" instead of running
        # understanding/vision straight away -- a bare photo often arrives
        # with no caption saying what it's for. See
        # interactions/image_purpose.py.
        image_purpose_reply = await try_hold_new_image_for_purpose_picker(
            message, user_id=ctx.user_id, pending_media_store=pending_media_store
        )
        timer.lap("image_purpose_picker")
        if image_purpose_reply is not None:
            await send_reply_spec(
                image_purpose_reply,
                wa_id,
                send_text=sender.send_text,
                send_list=sender.send_list,
                send_button=sender.send_button,
            )
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=image_purpose_reply.text
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
            return

        category_hint = await category_hint_store.pop_hint(user_id=ctx.user_id)
        timer.lap("pop_category_hint")
        # #6 Undo: a bare "undo"/"delete that" (mesiri_ai.undo_classifier) --
        # deterministic, zero-cost, same principle as the greeting/whoami
        # triggers above. Checked THIS message's own text directly (unlike
        # category_hint, which biases the NEXT message) and wins over any
        # stale category_hint from an unrelated earlier tap -- an explicit
        # "undo" right now must not be diluted by a leftover hint.
        undo_hint = (
            UNDO_SEMANTIC_HINT
            if message.modality is InputModality.TEXT and is_undo_trigger(message.text)
            else None
        )
        _fire_processing_ack(wa_id, message.modality)
        await process_inbound_message(
            message,
            actor_user_id=ctx.user_id,
            actor=ctx,
            semantic_hint=undo_hint or (category_hint.semantic_hint if category_hint else None),
            direction_hint=category_hint.direction if category_hint else None,
            category_hint_store=category_hint_store,
            pipeline=pipeline,
            context_resolver=context_resolver,
            planner=planner,
            workflow_runtime=workflow_runtime,
            interaction_handler=interaction_handler,
            send_text=sender.send_text_capturing_id,
            send_list=sender.send_list,
            send_button=sender.send_button,
            send_image=sender.send_image,
            send_document=sender.send_document,
            object_storage=object_storage,
            context_debug=settings.context_debug,
            message_logger=message_logger,
            trace_logger=trace_logger,
            inventory_query=inventory_query,
            catalog_query=catalog_query,
            org_settings_query=org_settings_query,
            expense_category_query=expense_category_query,
            money_account_query=money_account_query,
            petty_cash_query=petty_cash_query,
            reversal_query=reversal_query,
            site_issue_query=site_issue_query,
            duplicate_expense_query=duplicate_expense_query,
            workforce_query=workforce_query,
            activity_query=activity_query,
            labour_query_service=labour_query_service,
            activity_search_service=activity_search_service,
            dpr_request_query=dpr_request_query,
            vendor_query=vendor_query,
            expense_query_service=expense_query_service,
            pending_report_store=pending_report_store,
            memory_loader=memory_loader,
            memory_coordinator=memory_coordinator,
            batch_store=batch_store,
            escalation_query=escalation_query,
        )
        timer.lap("process_inbound_message")

    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
        object_storage=object_storage,
        on_normalized=_on_normalized,
        on_message_claimed=_mark_read_on_claim,
        trace_logger=trace_logger,
    )
    return AppContainer(
        settings=settings,
        http_client=http_client,
        deduplication_store=deduplication_store,
        message_store=message_store,
        receiver=receiver,
        context_resolver=context_resolver,
        pipeline=pipeline,
        planner=planner,
        actor_reader=actor_reader,
        inventory_query=inventory_query,
        catalog_query=catalog_query,
        org_settings_query=org_settings_query,
        expense_category_query=expense_category_query,
        object_storage=object_storage,
        receipt_renderer=receipt_renderer,
        workflow_runtime=workflow_runtime,
        interaction_handler=interaction_handler,
        redis_client=redis_client,
        message_logger=message_logger,
        trace_logger=trace_logger,
        material_db=material_db,
    )


def get_settings(request: Request) -> Settings:
    """Resolve application settings from the dependency container."""
    return get_container(request).settings


def get_container(request: Request) -> AppContainer:
    """Resolve the dependency container from the FastAPI application state."""
    return request.app.state.container


def get_receiver(request: Request) -> WhatsAppReceiver:
    """Resolve the WhatsApp ingress receiver."""
    return get_container(request).receiver
