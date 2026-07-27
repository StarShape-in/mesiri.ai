"""Progress Application Commands — the typed handoff from ConfirmedActionV2.

Placed here rather than under the backend's application package, matching
Material and Labour (see labour.py's docstring: "where Material and Expense
disagree ... follow Material" — commands are shared contract surface, not
backend-internal).

Two commands, not one, because Activity creation and a Progress Update are
structurally different acts (docs/execution/DAILY_REPORTING_PLAN.md ADR-D1,
ADR-D12): creating an Activity carries the full header (location, work
package, contractor, initial quantities); appending a Progress Update carries
only what changed at that moment, against an activity that already exists.
Collapsing them into one command with optional fields would blur exactly the
distinction P1 depends on — an Activity's header is mutable (via a
correction, see ADR-D14), a Progress Update never is.

`work_type` is free text in V1 (plan open decision #4) — no catalog exists to
validate it against, unlike Material's `material_name`. `unit`/`unit_id`
follow Material's exact resolution shape: `unit` is what the user said,
`unit_id` is filled in by the Handler's resolver
(application/progress/resolution.py) before persistence, reusing
`units_of_measure`/`unit_aliases` (0290) rather than building a second
resolution path.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v2.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from mesiri_contracts.assistant.v2.uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class ActivityQuantityInput(BaseModel):
    """One measured quantity reported against an Activity or a Progress Update.

    An Activity can carry zero of these (P10 — a narrative-only report is a
    valid record) or several (e.g. "180 sqm plastered, 2 doors fixed" in one
    message).
    """

    version: str = CONTRACT_VERSION

    #: Free text in V1 — see module docstring.
    work_type: str | None = None

    #: What the user said (e.g. "sqm", "bags"). Resolved to unit_id by the
    #: Handler before persistence; never resolved by AI (plan P5's sibling
    #: rule for quantities — only *planned* quantities are barred from AI
    #: inference, but unit *spelling* resolution is deterministic lookup,
    #: not inference, so it is fine to do here).
    unit: str
    unit_id: CanonicalUuid | None = None

    quantity: Decimal

    #: ACHIEVED ("180 today") vs CUMULATIVE ("1840 to date") — see plan §6.3.
    measurement_type: str = "ACHIEVED"

    model_config = {"extra": "forbid"}


class CreateActivityCommand(BaseModel):
    """Create a new Activity — the default path when no open activity matches
    (plan §1B.1, `activity_creation` graph)."""

    version: str = CONTRACT_VERSION

    command_id: str
    idempotency_key: str
    correlation_id: str

    organization_id: CanonicalUuid
    project_id: CanonicalUuid | None
    site_id: CanonicalUuid | None

    #: Nullable — P4: capture must work with zero Work Package/Location
    #: configuration. Backfillable from the dashboard later.
    work_package_id: CanonicalUuid | None = None
    location_id: CanonicalUuid | None = None

    work_type: str | None = None
    narrative: str | None = None
    contractor: str | None = None

    started_at: str | None = None  # "HH:MM", optional
    ended_at: str | None = None

    quantities: list[ActivityQuantityInput] = []

    activity_date: date
    occurred_date_source: str = "inferred_at_confirmation"

    #: "whatsapp_text" | "whatsapp_voice" | "whatsapp_image" | "dashboard" —
    #: same provenance metadata shape as Labour's `recorded_via`.
    source: str = "whatsapp_text"

    created_by: CanonicalUuid

    model_config = {"extra": "forbid"}


class AddProgressUpdateCommand(BaseModel):
    """Append a Progress Update to an existing Activity (plan §1B.1,
    `activity_continuation` graph). Never edits the Activity or a prior
    update — P1."""

    version: str = CONTRACT_VERSION

    command_id: str
    idempotency_key: str
    correlation_id: str

    organization_id: CanonicalUuid
    activity_id: CanonicalUuid

    #: STARTED | PROGRESS | PAUSED | RESUMED | COMPLETED | NOTE
    update_kind: str

    narrative: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_id: CanonicalUuid | None = None

    occurred_at: datetime

    source: str = "whatsapp_text"

    created_by: CanonicalUuid

    model_config = {"extra": "forbid"}
