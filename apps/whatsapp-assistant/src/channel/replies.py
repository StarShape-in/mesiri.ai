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

_EXAMPLES = (
    '  • "50 bags of cement arrived"\n'
    '  • "20 bags of cement used for the foundation"'
)


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
    case); every other reply is plain text with `list_rows=None`. The
    caller (runtime/inbound_journey.py) picks send_text vs send_list based
    on which is populated -- render_* functions never touch the transport."""

    text: str
    list_button_label: str | None = None
    list_rows: tuple[ListRow, ...] | None = None


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
_CATEGORY_PROMPTS: dict[str, str] = {
    "cat_material": (
        f'Tell me about the material — for example:\n{_EXAMPLES}'
    ),
    "cat_equipment": 'Tell me about the equipment — for example:\n  • "JCB ran for 4 hours"',
    "cat_labour": 'Tell me the headcount — for example:\n  • "12 workers on site today"',
    "cat_expense": 'Tell me the expense — for example:\n  • "Paid 1500 to ABC Hardware"',
}

# Field names as a site worker would say them, not as the schema spells them.
_FIELD_LABELS: dict[str, str] = {
    "material_name": "which material",
    "quantity": "how much",
    "unit": "the unit (bags, kg, tons)",
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


def render_greeting_menu(*, timezone: str | None = None, is_first_message: bool = False) -> ReplySpec:
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


def render_category_prompt(row_id: str) -> str | None:
    """The follow-up question after a category is tapped. Deterministic --
    no AI call, since we defined these row ids ourselves (see
    runtime/dependencies.py's category-tap fast path). None for an id that
    doesn't match a known category (stale/foreign button, tampered payload)."""
    return _CATEGORY_PROMPTS.get(row_id)


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
