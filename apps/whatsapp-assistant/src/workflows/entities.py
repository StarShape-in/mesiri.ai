"""EntityType — registry-local metadata for the composite-request plan layer
and the entity-resolution layer (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md
§4.2, docs/execution/ENTITY_RESOLUTION_PLAN.md §7.3).

Deliberately *not* in mesiri_contracts, mirroring WorkflowCategory's own
reasoning in registry.py: no Planner/Runtime contract crosses this boundary,
so it must not become a wire-level enum another service can couple to. If a
backend resolver ever keys off this directly, that decision moves it.

Two readers, one table (registry.py's provides/requires fields):
  - the entity-resolution layer reads it backwards: "a USER is missing --
    which workflow provides one?" (workflow_that_provides below)
  - the composite-request plan layer reads it forwards: "these steps -- what
    order?" (workflows/planning/ordering.py's topological sort, which in
    practice derives order from explicit StepRefs rather than this table --
    see that module's docstring)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntityType(str, Enum):
    """A named thing a workflow either produces or needs already resolved.

    Members correspond exactly to the WorkflowKeys registered with a
    non-empty `provides` in registry.py -- do not add a member here without
    also declaring which workflow provides it.
    """

    PROJECT = "project"
    SITE = "site"
    USER = "user"
    MEMBERSHIP = "membership"
    ACTIVITY = "activity"


# ---------------------------------------------------------------------------
# Resolution outcome -- docs/execution/ENTITY_RESOLUTION_PLAN.md §3.1.
#
# What resolving a name hint against an org's real rows comes back as. Pure,
# I/O-free data: producing one of these (querying a database, scoring
# candidates) is a runtime-layer concern kept in
# runtime/entity_resolution/member_resolution.py, the same separation
# workflow nodes keep between "decide" and "look up" (workflows/runtime.py's
# rule that a node itself never does I/O).
#
# This is the half of the vocabulary the composite-request plan layer
# explicitly defers to this doc (COMPOSITE_REQUEST_PLAN_LAYER.md §4.5) --
# EntityType above is shared; Resolved/Ambiguous/Missing exist only here.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Candidate:
    """One near-match offered to the user for confirmation. Never carries
    enough on its own to be acted on silently -- see Ambiguous below."""

    entity_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class Resolved:
    """Exactly one active entity matched the name -- carry on unchanged."""

    entity_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class Ambiguous:
    """One or more near-matches, none certain enough to use silently.

    Always resolved by a tappable picker, never auto-accepted -- the same
    principle `find_by_name_fuzzy`'s docstring states for the materials
    catalog ("substring/ILIKE match... never auto-accepted"), applied here
    with a different matching technique for a different reason: see
    runtime/entity_resolution/member_resolution.py's module docstring for why
    genuine near-match scoring is used for a person's name where
    workforce/matching.py's match_worker explicitly rejects it for labour
    attendance.
    """

    candidates: tuple[Candidate, ...]


@dataclass(frozen=True, slots=True)
class Missing:
    """Nothing matched, close or otherwise. Carries the name hint back so
    the caller can offer to create an entity with this exact name -- never
    invented (ADR-E4 in ENTITY_RESOLUTION_PLAN.md: Missing always offers,
    never auto-creates)."""

    name_hint: str


#: What resolving a named entity against an org's real data can come back
#: as.
ResolutionOutcome = Resolved | Ambiguous | Missing
