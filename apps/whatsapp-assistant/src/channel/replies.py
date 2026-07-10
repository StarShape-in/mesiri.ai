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

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2

_EXAMPLES = (
    '  • "50 bags of cement arrived"\n'
    '  • "20 bags of cement used for the foundation"'
)

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


def render_direct_reply(decision: PlannerDecisionV2, *, timezone: str | None = None) -> str:
    """Reply when there is no workflow to start: a greeting, a question, or
    something the assistant could not place."""
    if decision.reason is CanonicalEventType.GENERAL_QUESTION_ASKED:
        return (
            "I can record what arrives on site and what gets used. "
            f"For example:\n{_EXAMPLES}"
        )
    # UNRECOGNIZED — greetings land here, as does anything unparseable.
    return (
        f"{_greeting(timezone)}. Tell me what arrived or what was used on site.\n"
        f"For example:\n{_EXAMPLES}"
    )


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
