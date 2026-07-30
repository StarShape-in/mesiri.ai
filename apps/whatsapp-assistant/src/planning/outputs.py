"""What a completed PlanStep publishes for later steps to reference
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §7.2).

The missing half of StepRef. `planning/binding.py` resolves a
``StepRef(step_id, output_key)`` by looking up ``outputs[output_key]`` on the
step it names -- but nothing generic ever *populated* those outputs. Until
this module existed there was exactly one `mark_step_done` call in the
codebase, hardcoded to the member-create chain's create-user step with
hardcoded keys, so a decomposed plan's ``StepRef("s1", "project_id")`` would
have raised UnresolvedStepRefError at runtime no matter how correct the
linking was.

Two kinds of output, both needed by real chains:

1. **The created row's id**, named after what the workflow ``provides`` in
   workflows/registry.py -- PROJECT_CREATE provides PROJECT, so it publishes
   ``project_id``. The value is ``ExecutionResult.material_row_id``, which
   despite its materials-era name is the generic "id of the row this
   execution wrote" (the contract's own validator requires it on every
   SUCCEEDED/ALREADY_EXECUTED result, and identity/fakes.py already sets it
   for a created user). Derived from `provides` rather than a hand-written
   per-workflow table so a new entity type wires itself, exactly as
   `workflow_that_provides` does for the entity-resolution layer.

2. **The confirmed draft's own scalar fields**, echoed as-is. This is what
   makes the member-create chain work: ADD_PROJECT_MEMBER references
   ``StepRef(create_user, "full_name")`` because it needs the exact NAME the
   user was created under -- "Hisham", the picker-corrected spelling -- not
   the id and not the original mistranslated hint. Any later step can
   reference any field the producing step actually confirmed, which is a
   predictable contract and needs no per-pair wiring.

Only scalars are published: a draft field holding a list or dict (labour's
``lines``, for instance) is structure no StepRef can meaningfully name, and
copying it would bloat a Redis value that a plan carries for 30 minutes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey

#: Draft fields never worth republishing as plan outputs. `created_by_role`
#: and `role` describe the ACTOR's authority for that one step, not the
#: entity it created -- a later step inheriting them by reference would be
#: carrying the wrong step's permissions context. Both are always re-derived
#: per step from the plan's own actor instead.
_EXCLUDED_DRAFT_FIELDS = frozenset({"created_by_role"})

_SCALAR_TYPES = (str, int, float, bool)


def build_step_outputs(
    *,
    workflow_key: WorkflowKey,
    row_id: str | None,
    draft_fields: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """The outputs a just-completed step publishes.

    ``row_id`` is ``ExecutionResult.material_row_id`` (None only for a
    workflow that wrote no row -- an informational step, or one that
    completed without a draft; such a step simply publishes no id, and a
    StepRef naming one fails loudly in binding.py rather than silently
    resolving to None).

    Pure: no I/O, no Redis, no contract objects beyond WorkflowKey, so the
    mapping can be unit-tested against every registered workflow directly.
    """
    # Lazy, matching planning/decomposition.py's identical import -- keeps
    # planning/ free of a module-import-time dependency on registry.py's
    # full graph-builder import chain.
    from workflows.registry import get_definition

    outputs: dict[str, str] = {}

    definition = get_definition(workflow_key)
    if definition is not None and row_id:
        for entity in definition.provides:
            # EntityType values are the bare noun ("project", "user"), so the
            # id key is uniformly "<noun>_id" -- the same name a consuming
            # step's `scope` uses (project_id/site_id) and the same one
            # PlanStep.scope validates against SCOPE_KEYS.
            outputs[f"{entity.value}_id"] = str(row_id)

    for key, value in (draft_fields or {}).items():
        if key in _EXCLUDED_DRAFT_FIELDS or key in outputs:
            continue
        # `bool` is a subclass of int, so it is covered by _SCALAR_TYPES and
        # stringifies predictably; None is skipped so an absent field is
        # absent rather than the literal "None".
        if value is None or not isinstance(value, _SCALAR_TYPES):
            continue
        outputs[key] = str(value)

    return outputs
