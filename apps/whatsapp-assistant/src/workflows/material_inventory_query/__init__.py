"""material_inventory_query -- read-only material stock/history lookup.

Same shape as workflows/who_am_i: a single-node, stateless LangGraph graph
with no draft_action and no confirmation. Nothing here writes a business
record, so WorkflowRuntime treats a missing draft_action as COMPLETED rather
than AWAITING_CONFIRMATION.
"""

from __future__ import annotations
