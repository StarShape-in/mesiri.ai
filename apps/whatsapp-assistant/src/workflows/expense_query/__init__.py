"""expense_query -- read-only expense list/sum lookup.

Same shape as workflows/material_inventory_query: a single-node, stateless
LangGraph graph with no draft_action and no confirmation.
"""

from __future__ import annotations
