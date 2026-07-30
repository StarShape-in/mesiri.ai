"""Plan / PlanStep / StepRef — the shared data structures for a composite
request (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §6).

A Plan replaces two things that would otherwise stay separate: a decomposed
multi-intent message (this layer, §9) and a single intent that discovers a
missing prerequisite mid-flight (the entity-resolution layer,
docs/execution/ENTITY_RESOLUTION_PLAN.md). Per that doc's §4.4, the
entity-resolution layer's continuation is a Plan of size 1 with a step
inserted ahead of the blocked one -- not a separate mechanism. `origin`
exists so the two producers stay distinguishable in traces without being
distinguishable in machinery.

Ordering is not authored here. `topological_order` in ordering.py is the
only supported way to produce a Plan's `steps` tuple -- see that module's
docstring for why order is derived from explicit StepRefs rather than a
registry lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    # Set on a step whose transitive dependency failed -- never attempted
    # (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §7.4 / ADR-C4). Distinct
    # from FAILED: a FAILED step actually ran and did not succeed; a
    # CANCELLED step never ran at all.
    CANCELLED = "cancelled"


class PlanOrigin(str, Enum):
    #: Every step came from splitting one message into several intents.
    DECOMPOSITION = "decomposition"
    #: Every step came from a single intent hitting a missing prerequisite.
    RESOLUTION = "resolution"
    #: A decomposed plan that later had a resolution-inserted step spliced in.
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class StepRef:
    """A field value not known until an earlier step in the same plan has
    run. Resolved just-in-time, immediately before the referencing step is
    canonicalized and executed (ADR-C2) -- never eagerly, since the entity
    the ref points at (e.g. a brand-new project_id) does not exist until
    that earlier step's workflow actually completes."""

    step_id: str
    output_key: str

    def to_dict(self) -> dict[str, Any]:
        return {"__stepref__": True, "step_id": self.step_id, "output_key": self.output_key}

    @classmethod
    def is_encoded(cls, value: Any) -> bool:
        return isinstance(value, dict) and value.get("__stepref__") is True

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StepRef:
        return cls(step_id=raw["step_id"], output_key=raw["output_key"])


def _encode_field(value: Any) -> Any:
    return value.to_dict() if isinstance(value, StepRef) else value


def _decode_field(value: Any) -> Any:
    return StepRef.from_dict(value) if StepRef.is_encoded(value) else value


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One workflow to run as part of a Plan.

    ``fields`` are the extracted/known values for this step -- literals, or
    StepRef placeholders for values a prior step in the plan will produce.
    Never a full CanonicalEventV2: that is built just-in-time, once every
    StepRef here has resolved (see ADR-C2 in the plan-layer doc) -- building
    it eagerly is exactly the bug that makes "create Paraclette, then Tower B
    under it" fail today (site_create/nodes.py needs a real project_id that
    does not exist until step 1 has run).
    """

    step_id: str
    workflow_key: WorkflowKey
    fields: dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    #: Populated once this step reaches DONE -- feeds every StepRef pointing
    #: at this step_id in a later step's fields.
    outputs: dict[str, str] = field(default_factory=dict)
    #: The WorkflowInstance this step is actually running as, once started.
    #:
    #: Load-bearing, not bookkeeping: a plan outlives the turn that created
    #: it (PlanStore's 30-minute TTL), and a user can abandon a RUNNING step
    #: and later start a *different* workflow of the same key. Without this,
    #: "is this confirmation the one my plan is waiting for?" can only be
    #: answered by workflow_key + status, which matches any same-key
    #: workflow the user happens to confirm inside the TTL window -- the
    #: real bug this field was added to close (an abandoned "create Hysam"
    #: plan hijacking a later unrelated "create Rajesh" and offering Rajesh
    #: project-manager rights on Hysam's project). Every advance/resume
    #: decision must match on this, never on workflow_key alone.
    workflow_instance_id: str | None = None

    @property
    def depends_on(self) -> frozenset[str]:
        """step_ids this step cannot run before, derived from its own
        fields -- never authored separately (P2: order is derived, not
        stated). Only top-level field values are scanned; a StepRef nested
        inside a list or dict is out of scope for V1 (no current producer
        emits one)."""
        return frozenset(
            value.step_id for value in self.fields.values() if isinstance(value, StepRef)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "workflow_key": self.workflow_key.value,
            "fields": {k: _encode_field(v) for k, v in self.fields.items()},
            "status": self.status.value,
            "outputs": dict(self.outputs),
            "workflow_instance_id": self.workflow_instance_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanStep:
        return cls(
            step_id=raw["step_id"],
            workflow_key=WorkflowKey(raw["workflow_key"]),
            fields={k: _decode_field(v) for k, v in raw.get("fields", {}).items()},
            status=StepStatus(raw.get("status", StepStatus.PENDING.value)),
            outputs=dict(raw.get("outputs", {})),
            workflow_instance_id=raw.get("workflow_instance_id"),
        )


class DuplicateStepIdError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Plan:
    """A composite request: an ordered list of steps, one confirmation slot
    (workflows/runtime.py's single-active invariant is unaffected -- the
    Plan occupies the one AWAITING_CONFIRMATION slot; its steps do not each
    take one, see plan-layer doc §7.5/P6).

    ``steps`` must already be in a valid execution order -- produced by
    ordering.topological_order, never authored directly. This constructor
    only checks structural validity (no duplicate step_ids); it does NOT
    re-verify ordering or referential integrity, since re-deriving that here
    would duplicate ordering.py's one job. Callers that bypass
    topological_order are responsible for having called it themselves.
    """

    plan_id: str
    correlation_id: str
    user_id: str
    origin: PlanOrigin
    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise DuplicateStepIdError(
                    f"plan {self.plan_id}: duplicate step_id {step.step_id!r}"
                )
            seen.add(step.step_id)

    def step(self, step_id: str) -> PlanStep | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def with_steps(self, steps: tuple[PlanStep, ...]) -> Plan:
        """A copy of this plan with a replaced step list -- e.g. after
        marking one step DONE, or after ordering.topological_order re-sorts
        the list following a resolution-layer insertion."""
        return Plan(
            plan_id=self.plan_id,
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            origin=self.origin,
            steps=steps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "origin": self.origin.value,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Plan:
        return cls(
            plan_id=raw["plan_id"],
            correlation_id=raw["correlation_id"],
            user_id=raw["user_id"],
            origin=PlanOrigin(raw["origin"]),
            steps=tuple(PlanStep.from_dict(s) for s in raw.get("steps", [])),
        )
