"""InteractionHandler factory — consistent with build_context_resolver() and build_pipeline().

``build_container()`` in ``runtime/dependencies.py`` calls this rather than
constructing ``InteractionHandler`` inline, keeping the container clean and
making the dependency graph explicit.
"""

from __future__ import annotations

from memory.coordinator import ConversationMemoryCoordinator
from planner import Planner
from workflows import WorkflowRuntime
from workflows.batch_store import PendingBatchStore

from .classifier_port import InteractionClassifierPort
from .completion_photo_hint import CompletionPhotoHintStore
from .handler import InteractionHandler
from .ports import ExecutionDispatcher, ReceiptBuilder


def build_interaction_handler(
    workflow_runtime: WorkflowRuntime,
    classifier: InteractionClassifierPort | None = None,
    dispatcher: ExecutionDispatcher | None = None,
    receipt_builder: ReceiptBuilder | None = None,
    memory_coordinator: ConversationMemoryCoordinator | None = None,
    planner: Planner | None = None,
    batch_store: PendingBatchStore | None = None,
    completion_photo_hint_store: CompletionPhotoHintStore | None = None,
) -> InteractionHandler:
    """Construct an ``InteractionHandler`` wired to ``workflow_runtime`` and,
    once M8 is wired, an ``ExecutionDispatcher`` that executes confirmed
    Material actions synchronously in the same request, plus an optional
    ``ReceiptBuilder`` that renders the post-confirmation receipt image, an
    optional ``ConversationMemoryCoordinator`` (M19) that remembers the
    activity a confirmed CREATE_ACTIVITY/ADD_PROGRESS_UPDATE touched,
    ``planner``/``batch_store`` (#1 Multi-Activity) needed to start the next
    queued segment once a batch member's confirmation resolves, and
    ``completion_photo_hint_store`` (#25 AI Follow-up) needed to remember
    which Activity a proactive "want to attach a completion photo?" offer
    was about."""
    return InteractionHandler(
        workflow_runtime,
        classifier=classifier,
        dispatcher=dispatcher,
        receipt_builder=receipt_builder,
        memory_coordinator=memory_coordinator,
        planner=planner,
        batch_store=batch_store,
        completion_photo_hint_store=completion_photo_hint_store,
    )
