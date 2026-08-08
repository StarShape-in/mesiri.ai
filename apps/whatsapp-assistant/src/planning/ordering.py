"""Topological ordering of plan steps
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §7.1, P2).

Order is derived, never authored: nowhere does any module contain the
sentence "site after project." Concretely, this derives order from the
explicit StepRef placeholders a decomposer (or the entity-resolution layer)
already put in a step's fields -- NOT from a separate lookup against
workflows/registry.py's `provides`/`requires`. That registry pair answers a
different question ("which workflow provides a USER?", read backwards by the
entity-resolution layer) and is used earlier, by whatever assembles a step's
fields, to decide which prior step's output a field should reference in the
first place. By the time topological_order runs, every cross-step dependency
is already a concrete StepRef -- ordering just has to respect it.
"""

from __future__ import annotations

from collections.abc import Sequence

from .plan import PlanStep


class PlanUnresolvedRefError(ValueError):
    """A step's StepRef points at a step_id absent from this plan.

    Distinct from a Missing entity (docs/execution/ENTITY_RESOLUTION_PLAN.md):
    that is a real-world name that doesn't resolve to a database row. This is
    a plan-construction bug -- a StepRef naming a step that was never added
    to the plan at all -- and should never reach a user; it means whatever
    assembled the steps (the decomposer, or a resolution-layer insertion) is
    broken.
    """


class PlanCycleError(ValueError):
    """No valid order exists -- some steps depend on each other, directly or
    transitively. Refuses the whole plan rather than executing a prefix of
    it (plan-layer doc §7.1)."""


def topological_order(steps: Sequence[PlanStep]) -> tuple[PlanStep, ...]:
    """Order ``steps`` so every StepRef a step's fields carry names a step
    that already ran. Stable: among steps that become eligible in the same
    pass, the original relative order is preserved, so a decomposer's own
    intent order survives wherever the dependency graph doesn't force a
    change.

    Raises PlanUnresolvedRefError for a StepRef naming a step_id not present
    in ``steps`` at all, and PlanCycleError when no valid order exists.
    Never returns a partial order -- a plan that can't be fully ordered is
    refused outright (P3: nothing is written before the user has seen the
    whole plan; ordering runs before that preview is even built)."""
    steps = list(steps)
    known_ids = {s.step_id for s in steps}

    for candidate in steps:
        unresolved = candidate.depends_on - known_ids
        if unresolved:
            raise PlanUnresolvedRefError(
                f"step {candidate.step_id!r} references step(s) "
                f"{sorted(unresolved)} not present in this plan"
            )

    ordered: list[PlanStep] = []
    done_ids: set[str] = set()
    remaining = steps
    while remaining:
        eligible = [s for s in remaining if s.depends_on <= done_ids]
        if not eligible:
            raise PlanCycleError(
                f"cycle detected among step(s): {[s.step_id for s in remaining]}"
            )
        ordered.extend(eligible)
        done_ids.update(s.step_id for s in eligible)
        eligible_ids = {s.step_id for s in eligible}
        remaining = [s for s in remaining if s.step_id not in eligible_ids]

    return tuple(ordered)
