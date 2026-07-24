"""Assistant reply rendering for the planner leg of the journey.

Counterpart to ``interactions/response_handler.py`` (which renders the
interaction leg). Both are pure string rendering: no business logic, no I/O.
Localisation and WhatsApp template migration happen here, not in callers.

Before this module the journey only acted on ``START_WORKFLOW``; ``CLARIFY``
and ``DIRECT_REPLY`` were computed, logged, and dropped, so every non-workflow
message fell through to ``understanding.runtime.format_reply`` -- a developer
diagnostic ("Type: unknown / Confidence: unusable") that was never meant to
reach a user.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2

_EXAMPLES = '  • "50 bags of cement arrived"\n  • "20 bags of cement used for the foundation"'


@dataclass(frozen=True, slots=True)
class ListRow:
    """One tappable option in a WhatsApp list menu. Channel-agnostic content
    (id/title/description) -- transport-specific length limits are enforced
    where this actually gets sent (channel/whatsapp/outbound.py), not here."""

    id: str
    title: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class ReplySpec:
    """What to send back, decoupled from how. `list_rows` is only ever set
    for the category-menu reply (see render_direct_reply's UNRECOGNIZED
    case); `buttons` is only ever set for a workflow confirmation prompt
    (see runtime/inbound_journey.py's _render_reply). At most one of the two
    is ever populated. The caller (runtime/inbound_journey.py) picks
    send_text vs send_list vs send_button based on which is set --
    render_* functions never touch the transport."""

    text: str
    list_button_label: str | None = None
    list_rows: tuple[ListRow, ...] | None = None
    buttons: tuple[ListRow, ...] | None = None


# The two reply buttons shown under every "Confirm this record?" prompt.
# Tapping one normalizes to NormalizedMessage.text = the title ("Yes"/"No"),
# which interactions/classifier.py already recognizes -- no new classification
# logic needed, only the send side.
CONFIRM_BUTTONS: tuple[ListRow, ...] = (
    ListRow("confirm_yes", "Yes"),
    ListRow("confirm_no", "No"),
)


# The four v1 domain modules, per the locked architecture scope (Material ·
# Equipment & Machinery · Labour · Expense). Row ids are matched verbatim in
# runtime/dependencies.py's category-tap fast path -- keep the two in sync.
CATEGORY_ROWS: tuple[ListRow, ...] = (
    ListRow("cat_material", "Material", "Arrived or used on site"),
    ListRow("cat_equipment", "Equipment & Machinery", "Usage, hours, movement"),
    ListRow("cat_labour", "Labour", "Headcount and attendance"),
    ListRow("cat_expense", "Expense", "Petty cash spent"),
)

# What to say once a category is picked -- deterministic, no AI involved (see
# runtime/dependencies.py). Keyed by the same row ids as CATEGORY_ROWS.
# "cat_material" is handled separately (see render_category_prompt) -- it asks
# Arrived/Used up front instead of a text prompt, so that field never has to
# be inferred from speech at all on the common path (see MATERIAL_DIRECTION_
# BUTTONS below).
_CATEGORY_PROMPTS: dict[str, str] = {
    "cat_equipment": 'Tell me about the equipment — for example:\n  • "JCB ran for 4 hours"',
    "cat_labour": 'Tell me the headcount — for example:\n  • "12 workers on site today"',
    "cat_expense": 'Tell me the expense — for example:\n  • "Paid 1500 to ABC Hardware"',
}

# Tapping "Material" asks this before anything else -- a button tap can't be
# garbled by a translation error the way speech/text can, so locking direction
# here means the common path never depends on transcription quality for this
# field. Row ids are matched verbatim by runtime/dependencies.py's category-tap
# handler (kept distinct from _MATERIAL_ROW_PREFIX = "mat_" in inbound_journey
# .py, which prefixes catalog *material* ids -- no collision).
MATERIAL_DIRECTION_BUTTONS: tuple[ListRow, ...] = (
    ListRow("dir_received", "Arrived"),
    ListRow("dir_used", "Used"),
)

_MATERIAL_ARRIVED_PROMPT = '📦 *Material Arrived* — tell me what arrived.\n\n"50 bags of cement arrived"'
_MATERIAL_USED_PROMPT = (
    '📦 *Material Used* — tell me what was used.\n\n"20 bags of cement used for the foundation"'
)


def render_material_direction_followup(direction: str) -> str:
    """The tailored prompt shown right after a Material direction button tap
    -- the example no longer needs to mention arrived/used since that's
    already settled, only what/how much."""
    return _MATERIAL_ARRIVED_PROMPT if direction == "received" else _MATERIAL_USED_PROMPT

# The semantic_type a category tap hints extraction toward for the user's
# *next* message (see interactions/category_hint.py). A hint only ever
# nudges classification -- the model can still override it if the text
# clearly says otherwise (see the extraction prompts).
CATEGORY_SEMANTIC_HINT: dict[str, str] = {
    "cat_material": "material_update",
    "cat_equipment": "equipment_usage",
    "cat_labour": "labour_update",
    "cat_expense": "expense",
}

# Field names as a site worker would say them, not as the schema spells them.
_FIELD_LABELS: dict[str, str] = {
    "material_name": "which material",
    "quantity": "how much",
    "unit": "the unit (bags, kg, tons)",
    "direction": "whether it arrived or was used",
    "amount": "the amount",
    "equipment_name": "which equipment",
    "duration_hours": "how many hours",
    "headcount": "how many workers",
    "supplier": "the supplier",
    "work_item": "what it was used for",
}


def _label(field: str) -> str:
    return _FIELD_LABELS.get(field, field.replace("_", " "))


def _greeting(timezone: str | None) -> str:
    """Time-of-day greeting in the user's timezone.

    Falls back to a neutral "Hello" rather than guessing: a wrong "Good morning"
    at 9pm is worse than no greeting at all.
    """
    if not timezone:
        return "Hello"
    try:
        hour = datetime.now(ZoneInfo(timezone)).hour
    except (ZoneInfoNotFoundError, ValueError):
        return "Hello"
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def render_clarify_reply(decision: PlannerDecisionV2) -> str:
    """Ask for the fields that are missing before the report can be recorded.

    ``missing_fields`` is never empty for a CLARIFY decision -- canonicalization
    only sets CLARIFICATION_REQUIRED when at least one required field is absent
    -- but render a safe fallback rather than an empty question if that changes.
    """
    missing = [_label(f) for f in decision.missing_fields]
    if not missing:
        return "I didn't quite catch that. Could you say it again?"
    if len(missing) == 1:
        asked = missing[0]
    else:
        asked = f"{', '.join(missing[:-1])} and {missing[-1]}"
    return f"Almost there — I still need {asked}."


def render_project_picker(projects: list[tuple[str, str, str | None]]) -> ReplySpec:
    """Ask which project a report belongs to. ``projects`` is a list of
    (project_id, name, location) -- plain tuples, not backend.ports.ProjectSummary,
    so this module stays within the channel/ dependency rule (mesiri_contracts.*
    only). Row id is "proj_{project_id}", matched verbatim by the caller that
    resumes the pending report once one is tapped."""
    rows = tuple(
        ListRow(f"proj_{project_id}", name, location or "")
        for project_id, name, location in projects[:10]
    )
    return ReplySpec(
        text="Which project is this for?",
        list_button_label="Choose project",
        list_rows=rows,
    )


def render_no_projects_reply() -> str:
    """The sender has no project to attach a report to at all -- distinct from
    the picker case so the message doesn't imply tapping will help."""
    return "You don't have any projects assigned yet. Ask your admin to add you to one first."


def render_material_picker(candidates: list[tuple[str, str]]) -> ReplySpec:
    """Ask which catalog material a report refers to -- either because the
    reported name matched more than one active entry ("cement" -> OPC/PPC
    Cement) or none at all (falls back to the org's whole active catalog so
    there's still something to pick from). ``candidates`` is (material_id,
    name) pairs. Row id is "mat_{material_id}", matched verbatim by
    resume_pending_report_with_material once one is tapped."""
    rows = tuple(ListRow(f"mat_{material_id}", name) for material_id, name in candidates[:10])
    return ReplySpec(
        text="Which material do you mean?",
        list_button_label="Choose material",
        list_rows=rows,
    )


def render_material_not_found_reply(name: str) -> str:
    """No catalog material matched at all and the org's catalog is empty --
    distinct from the picker case for the same reason render_no_projects_reply
    is: tapping won't help, there's nothing to choose from."""
    return f'I couldn\'t find "{name}" in the materials catalog. Ask your admin to add it first.'


def render_unit_mismatch_reply(*, material_name: str, unit_id: str, unit_display: str) -> ReplySpec:
    """The reported unit doesn't match `material_name`'s Stock Unit (or wasn't
    recognized at all) -- ask a single yes/no clarification naming the
    material's actual unit, never a free-standing list of every unit in the
    system (a material only ever has one valid unit in V1, so a global picker
    would let the user pick something incompatible). Row ids "unit_yes_{id}"/
    "unit_no", matched verbatim by resume_pending_report_with_unit."""
    return ReplySpec(
        text=f"{material_name} is tracked in {unit_display} — record this as {unit_display}?",
        buttons=(ListRow(f"unit_yes_{unit_id}", "Yes"), ListRow("unit_no", "No")),
    )


def render_greeting_menu(
    *, timezone: str | None = None, is_first_message: bool = False
) -> ReplySpec:
    """The greeting + tappable category menu. Decision-independent (no
    PlannerDecisionV2 needed) so it can be called from two places: the AI
    path (render_direct_reply's UNRECOGNIZED case, below) and the
    deterministic pre-pipeline fast path (InteractionHandler.
    handle_greeting_trigger) that recognizes "hi"/"menu"/etc. without ever
    touching the AI pipeline. A first-ever message gets a short intro; a
    returning "hi" doesn't need re-introducing every time (see Infobip's
    greeting UX guidance).
    """
    if is_first_message:
        body = (
            f"{_greeting(timezone)}. I'm Mesiri — I record your daily site updates over "
            f"WhatsApp, no app needed. Just tell me what happened, like:\n{_EXAMPLES}\n\n"
            "Or pick what you're reporting:"
        )
    else:
        body = f"{_greeting(timezone)}. What are you reporting today?"

    return ReplySpec(
        text=body,
        list_button_label="Choose one",
        list_rows=CATEGORY_ROWS,
    )


def render_direct_reply(
    decision: PlannerDecisionV2, *, timezone: str | None = None, is_first_message: bool = False
) -> ReplySpec:
    """Reply when there is no workflow to start: a greeting, a question, or
    something the assistant could not place.

    Only the UNRECOGNIZED case ever carries a list menu -- greetings and
    unparseable text are exactly where a worker who doesn't know what to
    type benefits from tappable categories. A question that's already
    understood as a question doesn't need one.
    """
    if decision.reason is CanonicalEventType.GENERAL_QUESTION_ASKED:
        return ReplySpec(
            text=f"I can record what arrives on site and what gets used. For example:\n{_EXAMPLES}"
        )
    # UNRECOGNIZED — greetings land here (when they slip past the
    # deterministic fast path, e.g. text/handle_greeting_trigger didn't cover
    # every phrasing), as does anything genuinely unparseable.
    return render_greeting_menu(timezone=timezone, is_first_message=is_first_message)


def render_category_prompt(row_id: str) -> ReplySpec | None:
    """The follow-up question after a category is tapped. Deterministic --
    no AI call, since we defined these row ids ourselves (see
    runtime/dependencies.py's category-tap fast path). None for an id that
    doesn't match a known category (stale/foreign button, tampered payload).

    "cat_material" is the one category with a two-step tap (see
    MATERIAL_DIRECTION_BUTTONS) -- every other category still gets a single
    plain-text prompt, wrapped in a ReplySpec so the caller has one shape to
    dispatch regardless of which category was tapped."""
    if row_id == "cat_material":
        return ReplySpec(
            text="📦 *Material* — did it arrive on site, or get used?",
            buttons=MATERIAL_DIRECTION_BUTTONS,
        )
    text = _CATEGORY_PROMPTS.get(row_id)
    return ReplySpec(text=text) if text is not None else None


def render_understanding_failed_reply() -> str:
    """The AI could not make sense of the message at all (UNUSABLE confidence)."""
    return (
        "Sorry, I couldn't make out that message. Could you send it again — "
        "typed, or as a clearer voice note?"
    )


def render_unsupported_reply() -> str:
    """The intent was understood but no workflow exists for it yet.

    Distinct from ``render_understanding_failed_reply``: telling someone who
    reported an expense that we "couldn't make out" their message sends them
    rephrasing a message that was never the problem.
    """
    return "I understood that, but I can only record material updates right now."
