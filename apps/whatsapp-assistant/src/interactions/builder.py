"""InteractionHandler factory — consistent with build_context_resolver() and build_pipeline().

``build_container()`` in ``runtime/dependencies.py`` calls this rather than
constructing ``InteractionHandler`` inline, keeping the container clean and
making the dependency graph explicit.
"""

from __future__ import annotations

from workflows import WorkflowRuntime

from .classifier_port import InteractionClassifierPort
from .handler import InteractionHandler
from .ports import ExecutionDispatcher


def build_interaction_handler(
    workflow_runtime: WorkflowRuntime,
    classifier: InteractionClassifierPort | None = None,
    dispatcher: ExecutionDispatcher | None = None,
) -> InteractionHandler:
    """Construct an ``InteractionHandler`` wired to ``workflow_runtime`` and,
    once M8 is wired, an ``ExecutionDispatcher`` that executes confirmed
    Material actions synchronously in the same request."""
    return InteractionHandler(workflow_runtime, classifier=classifier, dispatcher=dispatcher)
