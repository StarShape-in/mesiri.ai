"""Just-in-time reference resolution and event construction (ADR-C2,
docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §7.2, §11.1).

This is the module that closes both gaps the first cut of `planning/`
shipped with:

(a) A `PlanStep` on its own cannot rebuild a `CanonicalEventV2` --
    `workflow_key` -> `event_type` is many-to-one (planner/routing.py:
    SITE_UPDATE <- 2 event types, SITE_ISSUE_CLOSE <- 3, PETTY_CASH <- 2,
    REVERSE <- 2), and org/permissions/conversation live on the Plan, not
    the step. `build_event` puts the two halves back together.

(b) A `StepRef`'s destination is not inferable from its name. A project
    reference belongs in `CanonicalEventV2.project_id`, NOT in `.fields` --
    site_create/nodes.py reads `state["project_id"]` and its docstring says
    plainly that the project comes from context resolution, *"never from
    collected_fields"*. `PlanStep` keeps `fields` and `scope` apart and this
    module applies each to the right place.

Why "just in time": the value a `StepRef` names does not exist until the
step it points at has actually run. "Create Paraclette, then Tower B under
it" cannot be canonicalized up front at any price -- the project_id is
created by step 1's execution. Everything here therefore runs immediately
before a step starts, never earlier.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.canonical_event import IntentCompleteness
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.common.ids import new_id

from .plan import Plan, PlanStep, StepRef, StepStatus


class UnresolvedStepRefError(ValueError):
    """A StepRef could not be resolved to a value.

    Always a bug rather than a user-facing condition: `topological_order`
    guarantees the referenced step ran first, and `PlanStore` only offers a
    step once its dependencies are DONE. Reaching this means the producing
    step completed without publishing the output key its consumer names --
    i.e. the two sides disagree about the contract, which is worth failing
    loudly on rather than silently substituting None and writing a record
    with a missing project.
    """


def outputs_by_step(plan: Plan) -> dict[str, dict[str, str]]:
    """Every completed step's published outputs, keyed by step_id."""
    return {s.step_id: dict(s.outputs) for s in plan.steps if s.status is StepStatus.DONE}


def resolve_value(value: Any, outputs: dict[str, dict[str, str]], *, where: str) -> Any:
    """Resolve one value: a StepRef becomes the referenced output, anything
    else passes through untouched."""
    if not isinstance(value, StepRef):
        return value
    produced = outputs.get(value.step_id)
    if produced is None or value.output_key not in produced:
        raise UnresolvedStepRefError(
            f"{where}: step {value.step_id!r} has not published {value.output_key!r} "
            f"(available: {sorted(produced) if produced else 'step not done'})"
        )
    return produced[value.output_key]


def resolve_step(step: PlanStep, plan: Plan) -> tuple[dict[str, Any], dict[str, Any]]:
    """This step's ``(fields, scope)`` with every StepRef replaced by the
    real value a prior step produced. Pure -- no I/O, no mutation."""
    outputs = outputs_by_step(plan)
    fields = {
        key: resolve_value(value, outputs, where=f"step {step.step_id!r} field {key!r}")
        for key, value in step.fields.items()
    }
    scope = {
        key: resolve_value(value, outputs, where=f"step {step.step_id!r} scope {key!r}")
        for key, value in step.scope.items()
    }
    return fields, scope


def build_event(step: PlanStep, plan: Plan, *, correlation_id: str | None = None) -> CanonicalEventV2:
    """The CanonicalEventV2 for ``step``, built the moment before it runs.

    Everything a workflow needs is reassembled here from the two places it
    legitimately lives: per-step data from the step (`event_type`, `fields`,
    `scope`) and per-request identity from the plan (`organization_id`,
    `user_id`, `permissions`, `conversation_id`, `source_message_id`). None
    of it is re-derived or re-resolved -- re-resolving permissions per step
    would let one plan half-execute under two different permission sets.

    ``correlation_id`` defaults to the plan's own, so every step of one
    composite request stays a single interaction in the logs viewer (the
    same grouping message_logger.set_interaction_group already relies on).

    Completeness is ACTIONABLE by construction: a step only exists because
    something decided this workflow should run, and every StepRef it
    depended on has just resolved. A step that still needs a field the user
    must supply is handled by the workflow's own build_draft asking for it
    (CREATE_USER asking for a phone number is exactly this), not by marking
    the event incomplete here.
    """
    fields, scope = resolve_step(step, plan)
    return CanonicalEventV2(
        event_id=new_id("evt"),
        correlation_id=correlation_id or plan.correlation_id,
        source_message_id=plan.source_message_id or plan.correlation_id,
        conversation_id=plan.conversation_id,
        event_type=step.event_type,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=plan.organization_id,
        user_id=plan.user_id,
        project_id=scope.get("project_id") or None,
        site_id=scope.get("site_id") or None,
        permissions=list(plan.permissions),
        fields=fields,
    )
