"""InteractionHandler factory — consistent with build_context_resolver() and build_pipeline().

``build_container()`` in ``runtime/dependencies.py`` calls this rather than
constructing ``InteractionHandler`` inline, keeping the container clean and
making the dependency graph explicit.
"""

from __future__ import annotations

from workflows import WorkflowRuntime

from .classifier_port import InteractionClassifierPort
from .handler import InteractionHandler
from .ports import ExecutionDispatcher, ReceiptBuilder


def build_interaction_handler(
    workflow_runtime: WorkflowRuntime,
    classifier: InteractionClassifierPort | None = None,
    dispatcher: ExecutionDispatcher | None = None,
    receipt_builder: ReceiptBuilder | None = None,
) -> InteractionHandler:
    """Construct an ``InteractionHandler`` wired to ``workflow_runtime`` and,
    once M8 is wired, an ``ExecutionDispatcher`` that executes confirmed
    Material actions synchronously in the same request, plus an optional
    ``ReceiptBuilder`` that renders the post-confirmation receipt image."""
    return InteractionHandler(
        workflow_runtime,
        classifier=classifier,
        dispatcher=dispatcher,
        receipt_builder=receipt_builder,
    )
