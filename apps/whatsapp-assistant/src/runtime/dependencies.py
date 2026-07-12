"""Application dependency wiring for the WhatsApp assistant runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingress.deduplication import InMemoryDeduplicationStore
from ingress.media_ingestion import MetaMediaDownloader
from ingress.receiver import InMemoryNormalizedMessageStore, WhatsAppReceiver
from runtime.logging_ports import MessageLogger, TraceLogger

if TYPE_CHECKING:
    from backend.ports import ActorReader
    from channel.receipt import ReceiptRenderer
    from context.resolver import ContextResolver
    from interactions import InteractionHandler
    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from planner import Planner
    from runtime.expense_category_query import ExpenseCategoryQueryService
    from runtime.inventory_query import MaterialInventoryQueryService
    from runtime.material_catalog_query import MaterialCatalogQueryService
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
    media_download_dir: str = "/tmp/mesiri/whatsapp-media"
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
    # Read-only expense category names for the extraction call's AI-side
    # category selection. Exposed for the same reason as catalog_query above.
    expense_category_query: ExpenseCategoryQueryService
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
        download_dir=Path(settings.media_download_dir),
        graph_base_url=settings.graph_base_url,
    )

    # M4 identity gate, then M2 -> M3 -> M4 Context resolver -> reply.
    import logging as _logging

    from backend.postgres.actor import PostgresActorReader
    from backend.postgres.message_logger import PostgresMessageLogger
    from backend.postgres.trace_logger import PostgresTraceLogger
    from backend.postgres.workflow_instance import PostgresWorkflowInstanceRepository
    from channel.replies import CATEGORY_SEMANTIC_HINT
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
    from planner import Planner
    from runtime.inbound_journey import (
        process_inbound_message,
        resume_pending_report_with_material,
        resume_pending_report_with_project,
        resume_pending_report_with_unit,
    )
    from runtime.reply_dispatch import send_reply_spec
    from understanding.runtime import build_pipeline
    from workflows import WorkflowRegistry, WorkflowRuntime

    _log = _logging.getLogger("mesiri.context")

    # Object storage: FakeObjectStorage locally, R2 when
    # MESIRI_OBJECT_STORAGE__PROVIDER=r2 is set.
    _backend_settings = _get_backend_settings()
    object_storage = build_object_storage(_backend_settings)

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
    from mesiri.infrastructure.postgres.repositories.expense_execution import (
        PostgresExpenseExecutionRepository,
    )

    expense_execution_handler = RecordExpenseHandler(
        PostgresExpenseExecutionRepository(),
        db=material_db,
        resolver=PostgresExpenseCategoryResolver(),
    )
    expense_dispatcher = ExpenseExecutionDispatcher(expense_execution_handler)
    # Routes a confirmed action to the dispatcher registered for its
    # action_type -- InteractionHandler only ever holds one ExecutionDispatcher.
    from interactions.execution_router import ActionTypeRoutingDispatcher
    from mesiri_contracts.assistant.draft_action import DraftActionType

    execution_dispatcher = ActionTypeRoutingDispatcher(
        {
            DraftActionType.RECORD_MATERIAL_RECEIPT: material_dispatcher,
            DraftActionType.RECORD_MATERIAL_USAGE: material_dispatcher,
            DraftActionType.RECORD_EXPENSE: expense_dispatcher,
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
    # Read-only expense category names, fed into the extraction call so the
    # AI can pick from the org's real categories -- same reasoning and same
    # material_db as catalog_query above. See runtime/expense_category_query.py.
    from runtime.expense_category_query import ExpenseCategoryQueryService

    expense_category_query = ExpenseCategoryQueryService(material_db)
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

    interaction_classifier = AdapterInteractionClassifier(
        DynamicAIProviderResolver(material_db, redis_client, _backend_settings)
    )
    # Post-confirmation receipt image (see AGENTS.md's Module Placement Log
    # and channel/receipt/). One long-lived headless-Chromium instance for
    # the whole process -- ReceiptRenderer launches it lazily on first
    # render, not here, so container construction never needs a browser
    # installed. Closed in runtime/lifecycle.py's shutdown handler.
    from channel.receipt import MaterialReceiptBuilder, ReceiptRenderer

    receipt_renderer = ReceiptRenderer()
    material_receipt_builder = MaterialReceiptBuilder(receipt_renderer)
    # M7: resolves a confirmation reply into the pending workflow, or None
    # (fall through to the normal understanding journey). M8: when a CONFIRM
    # resolves to CONFIRMED, the dispatcher executes the domain write
    # synchronously in the same request and the reply reflects the real outcome.
    interaction_handler = build_interaction_handler(
        workflow_runtime,
        classifier=interaction_classifier,
        dispatcher=execution_dispatcher,
        receipt_builder=material_receipt_builder,
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
    trace_logger: TraceLogger = PostgresTraceLogger()

    # _send_understanding_reply (the old reply_sender=... callback) is gone:
    # inbound_journey._render_reply() now covers every outcome, so the
    # understanding-only fallback it fed was dead weight.
    async def _on_normalized(message, raw_payload, retry_of_id=None) -> None:  # type: ignore[no-untyped-def]
        wa_id = message.sender.wa_id

        # M4: resolve the sender before spending on understanding.
        try:
            ctx = await resolve_sender(actor_reader, wa_id)
        except Exception:  # noqa: BLE001 — never let a lookup error drop the message silently
            _log.exception("context.identity_lookup_failed wa_id=%s", wa_id)
            ctx = None

        org_id = ctx.organization_id if ctx else None

        # Best-effort inbound message log (for debugging/replay). raw_payload
        # is a self-contained, replayable envelope of the raw Meta webhook
        # JSON (see ingress.receiver.WhatsAppReceiver._envelope) -- stored in
        # full so a failed message can later be replayed via the admin retry
        # action. A retry reuses the same WhatsApp message_id, so its dedup_key
        # is suffixed with the new correlation_id to avoid colliding with the
        # original row (ON CONFLICT (dedup_key) DO NOTHING would otherwise
        # silently drop the retry attempt).
        dedup_key = (
            message.message_id
            if retry_of_id is None
            else f"{message.message_id}:retry:{message.correlation_id}"
        )
        await message_logger.log_received(
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

        # M7: if the user has a workflow awaiting confirmation and this message
        # is a confirmation reply, resume it and stop — the AI pipeline (and its
        # token cost) is never touched. A plain "yes" ends here.
        try:
            handled = await interaction_handler.handle_fast_path(ctx.user_id, message, actor=ctx)
        except Exception:  # noqa: BLE001 — a resume error must not drop the message
            _log.exception("interaction.handle_failed user=%s", ctx.user_id)
            handled = None
        if handled is not None:
            if handled.reply_image is not None:
                sent = await sender.send_image(
                    wa_id, handled.reply_image, caption=handled.reply_text
                )
                if not sent:
                    await sender.send_text(wa_id, handled.reply_text)
            else:
                await sender.send_text(wa_id, handled.reply_text)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=handled.reply_text
            )
            await message_logger.update_context(
                correlation_id=message.correlation_id,
                project_id=handled.project_id,
                site_id=handled.site_id,
            )
            await message_logger.mark_completed(correlation_id=message.correlation_id)
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
            await sender.send_text(wa_id, category_prompt)
            await message_logger.log_reply(
                correlation_id=message.correlation_id, reply=category_prompt
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
            message_logger=message_logger,
        )
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
            message_logger=message_logger,
        )
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
            message_logger=message_logger,
        )
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

        semantic_hint = await category_hint_store.pop_hint(user_id=ctx.user_id)
        await process_inbound_message(
            message,
            actor_user_id=ctx.user_id,
            actor=ctx,
            semantic_hint=semantic_hint,
            category_hint_store=category_hint_store,
            pipeline=pipeline,
            context_resolver=context_resolver,
            planner=planner,
            workflow_runtime=workflow_runtime,
            interaction_handler=interaction_handler,
            send_text=sender.send_text,
            send_list=sender.send_list,
            send_button=sender.send_button,
            send_image=sender.send_image,
            context_debug=settings.context_debug,
            message_logger=message_logger,
            trace_logger=trace_logger,
            inventory_query=inventory_query,
            catalog_query=catalog_query,
            expense_category_query=expense_category_query,
            pending_report_store=pending_report_store,
        )

    receiver = WhatsAppReceiver(
        deduplication_store=deduplication_store,
        media_downloader=media_downloader,
        message_store=message_store,
        object_storage=object_storage,
        on_normalized=_on_normalized,
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
        expense_category_query=expense_category_query,
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
