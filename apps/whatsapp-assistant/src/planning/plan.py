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

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
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


#: The only two scope keys a step may carry. CanonicalEventV2's scope is
#: exactly project_id/site_id (organization_id and user_id are plan-level --
#: they cannot differ between steps of one message), and the model is
#: extra="forbid", so anything else here could never be applied.
SCOPE_KEYS = frozenset({"project_id", "site_id"})


class InvalidScopeKeyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One workflow to run as part of a Plan.

    Deliberately NOT a built CanonicalEventV2: that is constructed
    just-in-time by planning/binding.py, once every StepRef has resolved
    (ADR-C2). Building it eagerly is exactly what makes "create Paraclette,
    then Tower B under it" impossible -- site_create/nodes.py needs a real
    project_id that does not exist until step 1 has run.

    Two dicts, because a value's DESTINATION is not inferable from its name
    (plan-layer doc §11.1(b)):

    - ``fields`` -> CanonicalEventV2.fields, the extracted/collected values.
    - ``scope``  -> CanonicalEventV2.project_id / site_id.

    site_create/nodes.py reads ``state["project_id"]`` and its docstring is
    explicit that the project comes from context resolution, *"never from
    collected_fields"*. A project reference put in ``fields`` is silently
    ignored and the workflow asks "Which project should I add this site to?"
    -- reproducing the exact bug this layer exists to remove. Keeping the two
    apart makes that mistake unrepresentable rather than merely discouraged.

    Values in either dict may be a StepRef; ``depends_on`` scans both.
    """

    step_id: str
    workflow_key: WorkflowKey
    #: Not derivable from workflow_key: the mapping is many-to-one
    #: (planner/routing.py -- SITE_UPDATE <- 2 event types,
    #: SITE_ISSUE_CLOSE <- 3, PETTY_CASH <- 2, REVERSE <- 2), so a step that
    #: stored only the key could not rebuild the event its workflow needs.
    event_type: CanonicalEventType
    fields: dict[str, Any]
    #: project_id / site_id only -- see SCOPE_KEYS.
    scope: dict[str, Any] = field(default_factory=dict)
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

    def __post_init__(self) -> None:
        invalid = set(self.scope) - SCOPE_KEYS
        if invalid:
            raise InvalidScopeKeyError(
                f"step {self.step_id!r}: scope may only carry {sorted(SCOPE_KEYS)}, "
                f"got {sorted(invalid)} -- collected values belong in `fields`"
            )

    @property
    def depends_on(self) -> frozenset[str]:
        """step_ids this step cannot run before, derived from its own fields
        and scope -- never authored separately (P2: order is derived, not
        stated). Only top-level values are scanned; a StepRef nested inside a
        list or dict is out of scope for V1 (no current producer emits one)."""
        return frozenset(
            value.step_id
            for value in (*self.fields.values(), *self.scope.values())
            if isinstance(value, StepRef)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "workflow_key": self.workflow_key.value,
            "event_type": self.event_type.value,
            "fields": {k: _encode_field(v) for k, v in self.fields.items()},
            "scope": {k: _encode_field(v) for k, v in self.scope.items()},
            "status": self.status.value,
            "outputs": dict(self.outputs),
            "workflow_instance_id": self.workflow_instance_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanStep:
        return cls(
            step_id=raw["step_id"],
            workflow_key=WorkflowKey(raw["workflow_key"]),
            event_type=CanonicalEventType(raw["event_type"]),
            fields={k: _decode_field(v) for k, v in raw.get("fields", {}).items()},
            scope={k: _decode_field(v) for k, v in raw.get("scope", {}).items()},
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

    Identity/provenance lives HERE rather than on each step because it is
    genuinely plan-level: every step of one composite request shares the same
    sender, org, permissions and originating message. Storing it once is what
    lets planning/binding.py rebuild a complete CanonicalEventV2 per step
    (plan-layer doc §11.1(a)) instead of dropping organization_id,
    permissions and conversation_id on the floor the way the first cut did.
    """

    plan_id: str
    correlation_id: str
    user_id: str
    organization_id: str
    origin: PlanOrigin
    steps: tuple[PlanStep, ...]
    #: The message that produced this plan. Carried so every step's rebuilt
    #: event traces back to the same inbound message rather than inventing a
    #: fresh id per step.
    source_message_id: str = ""
    conversation_id: str | None = None
    #: The sender's permissions as resolved once, at plan time. Re-resolving
    #: per step would let a plan half-execute under two different permission
    #: sets if a role changed mid-plan.
    permissions: tuple[str, ...] = ()

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
        the list following a resolution-layer insertion.

        dataclasses.replace rather than a field-by-field rebuild: the same
        reasoning as PlanStore's status mutations. A rebuild silently drops
        any field added to Plan later, which is how organization_id/
        permissions would go missing the first time a step completed."""
        return dataclasses.replace(self, steps=steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "origin": self.origin.value,
            "source_message_id": self.source_message_id,
            "conversation_id": self.conversation_id,
            "permissions": list(self.permissions),
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Plan:
        return cls(
            plan_id=raw["plan_id"],
            correlation_id=raw["correlation_id"],
            user_id=raw["user_id"],
            organization_id=raw["organization_id"],
            origin=PlanOrigin(raw["origin"]),
            source_message_id=raw.get("source_message_id", ""),
            conversation_id=raw.get("conversation_id"),
            permissions=tuple(raw.get("permissions", ())),
            steps=tuple(PlanStep.from_dict(s) for s in raw.get("steps", [])),
        )
