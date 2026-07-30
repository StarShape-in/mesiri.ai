"""Entity resolution -- turning a free-text name hint into a real row, or
knowing honestly that it isn't one yet (docs/execution/ENTITY_RESOLUTION_PLAN.md).

Split from workflows/entities.py (the pure vocabulary: EntityType,
Resolved/Ambiguous/Missing) the same way understanding/ is split from
canonicalization/ -- this package does the I/O and the scoring; entities.py
stays pure so it can be imported from workflows/registry.py without pulling
a database dependency into the registry.
"""

from __future__ import annotations
