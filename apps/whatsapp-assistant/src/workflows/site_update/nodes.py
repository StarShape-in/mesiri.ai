"""Activity creation workflow nodes — pure functions, no LangGraph, no I/O, no SQL.

Mirrors workflows/material/nodes.py's shape: single-pass build_draft ->
request_confirmation, no slot-filling loop. Unlike Labour's worker matching,
nothing here needs to ask a mid-workflow disambiguation question in V1 --
location and work package resolution are resolution-gate concerns (plan
§1B.2, `workflows/shared/resolve_location.py`, not yet built) that run
*before* this graph via the same pattern Material's inbound_journey gate
uses, not inside it. This graph's only job is: build the draft from whatever
fields already made it through resolution, then show the confirmation.

P10 (optimize for speed of recording) governs every field here: a missing
quantity, location, or work package is never blocking. `application/progress/
mapper.py`'s `build_create_activity_command` and `domains/progress/
validation.py`'s `validate_create_activity` are what actually decide whether
a report is usable — this graph never repeats those rules, it only shapes
what the user is shown before confirming.
"""

from __future__ import annotations

from datetime import date

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.common.ids import new_id

from ..state import WorkflowGraphState


def build_draft(state: WorkflowGraphState) -> dict:
    """Map collected fields into a DraftAction. Shape-mapping only — no validation.

    Field names here (`work_type`, `quantities`, `narrative`, `location_id`,
    `work_package_id`, `contractor`, `activity_date`) are exactly what
    `application/progress/mapper.py`'s `build_create_activity_command` reads
    out of `confirmed.draft_action.fields` — this is the one place upstream
    of that mapper that decides the field names, so a rename on either side
    must change both.
    """
    fields = dict(state.get("collected_fields") or {})
    draft = DraftActionV2(
        draft_id=new_id("draft"),
        correlation_id=state["correlation_id"],
        workflow_instance_id=state["workflow_instance_id"],
        action_type=DraftActionType.CREATE_ACTIVITY,
        organization_id=state["organization_id"],
        user_id=state["user_id"],
        project_id=state.get("project_id"),
        site_id=state.get("site_id"),
        fields=fields,
    )
    return {"draft_action": draft}


# Rendered by dedicated lines below (quantities as a bulleted list, the date
# with its "(assumed today)" qualifier), not as raw key:value lines -- shown
# unformatted they would be unreadable exactly when the user most needs to
# check them. Internal plumbing fields are hidden outright.
_DISPLAY_HIDDEN_FIELD_KEYS = frozenset(
    {
        "quantities",
        "occurred_date",
        "occurred_date_source",
        "project_name",
        "site_name",
        "location_name",
        "work_package_name",
        "source",
        "work_type",
        "contractor",
        "narrative",
    }
)


def _date_line(fields: dict) -> str | None:
    """The day being recorded, marked when Mesiri guessed it. Same reasoning
    as Material's and Labour's equivalents (workflows/material/nodes.py,
    workflows/labour_update/nodes.py): a Progress Update can only append a
    correction, never edit the Activity's date, so confirmation is the one
    cheap moment to catch a wrong guess.

    Reads `occurred_date` (not `activity_date`, the DB column name) --
    canonicalization/occurred_date.py writes `occurred_date`/
    `occurred_date_source` onto every module's fields uniformly; `activity_date`
    is a Progress-specific rename that only happens later, in
    application/progress/mapper.py's `_activity_date`."""
    raw = str(fields.get("occurred_date") or "").strip()
    if not raw:
        return None
    try:
        shown = date.fromisoformat(raw).strftime("%d %b %Y")
    except ValueError:
        shown = raw
    if str(fields.get("occurred_date_source") or "") == "inferred_at_confirmation":
        return f"   • Date: {shown} (assumed today)"
    return f"   • Date: {shown}"


def _quantity_line(entry: dict) -> str | None:
    quantity = entry.get("quantity")
    unit = entry.get("unit")
    if quantity is None or not unit:
        return None
    work_type = entry.get("work_type")
    label = f"{quantity} {unit}"
    if work_type:
        label = f"{label} {work_type}"
    return f"   • {label}"


def request_confirmation(state: WorkflowGraphState) -> dict:
    """Compose the confirmation prompt — the gate nothing is persisted before
    (principle P2). Deterministic formatting only, matching every other v1
    workflow's confirmation node -- no localization/templates/AI generation.

    Project, site, location and work package are shown by name when the
    caller seeded them (`*_name` fields, mirroring Labour's project_name/
    site_name convention) and omitted otherwise: a bare UUID is worse than
    saying nothing, and a nullable location/work package (P4) is a normal,
    expected state for this confirmation to render correctly regardless.
    """
    draft: DraftActionV2 = state["draft_action"]
    fields = draft.fields

    out = ["*Confirm this record?*", "", "🏗️ Site Activity"]

    project_name = fields.get("project_name")
    site_name = fields.get("site_name")
    location_name = fields.get("location_name")
    work_package_name = fields.get("work_package_name")
    if project_name:
        out.append(f"   • Project: {project_name}")
    if site_name:
        out.append(f"   • Site: {site_name}")
    if location_name:
        out.append(f"   • Location: {location_name}")
    if work_package_name:
        out.append(f"   • Work Package: {work_package_name}")
    date_line = _date_line(fields)
    if date_line:
        out.append(date_line)

    work_type = fields.get("work_type")
    if work_type:
        out.append(f"   • Work: {work_type}")
    contractor = fields.get("contractor")
    if contractor:
        out.append(f"   • Contractor: {contractor}")

    narrative = fields.get("narrative")
    if narrative:
        out.append("")
        out.append(f"   \"{narrative}\"")

    quantities = fields.get("quantities")
    if isinstance(quantities, list) and quantities:
        out.append("")
        for entry in quantities:
            if isinstance(entry, dict):
                line = _quantity_line(entry)
                if line:
                    out.append(line)

    for key, value in fields.items():
        if key in _DISPLAY_HIDDEN_FIELD_KEYS:
            continue
        out.append(f"   • {key}: {value}")

    out.append("")
    out.append("Reply YES to confirm or NO to cancel.")
    return {"pending_prompt": "\n".join(out)}
