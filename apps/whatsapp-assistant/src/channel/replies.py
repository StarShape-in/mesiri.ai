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

# A photo's purpose is never assumed from the AI's own guess at what the
# image shows -- every genuinely new image (not a tap resuming this very
# picker) is held (see interactions/pending_media.py) and this list is sent
# first, since a bare photo often arrives with no caption at all. Deliberately
# narrow for now (Expense, Site Update) -- more purposes (attendance, etc.)
# get their own row here later, not a different mechanism.
IMAGE_PURPOSE_ROWS: tuple[ListRow, ...] = (
    ListRow("img_expense", "Expense", "Receipt or bill"),
    ListRow("img_site_update", "Site Update", "Progress photo"),
)

# The semantic_type an image-purpose tap hints extraction toward for the
# HELD image being re-processed (see interactions/image_purpose.py). Same
# nudge-not-authority principle as CATEGORY_SEMANTIC_HINT above.
IMAGE_PURPOSE_SEMANTIC_HINT: dict[str, str] = {
    "img_expense": "expense",
    "img_site_update": "general_site_update",
}


def render_image_purpose_picker() -> ReplySpec:
    return ReplySpec(
        text="📷 What is this photo for?",
        list_button_label="Choose one",
        list_rows=IMAGE_PURPOSE_ROWS,
    )


def render_image_purpose_coming_soon(row_id: str) -> str | None:
    """Site Update photos aren't processed yet -- an honest reply instead of
    a silent NO_GRAPH failure (WorkflowKey.SITE_UPDATE has no compiled graph
    today; that's separate, unrelated follow-up work, not an image gap).
    None for anything this function doesn't own (the caller only calls this
    for a row_id that isn't "img_expense")."""
    if row_id == "img_site_update":
        return "📷 Got it — site update photos aren't processed yet, but that's coming soon."
    return None


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


# Fixed id for "All Sites Combined" -- distinct from the per-site "site_{id}"
# prefix (never collides: real site ids are UUIDs, never the literal "all").
ALL_SITES_ROW_ID = "site_all"


def render_site_picker(sites: list[tuple[str, str]], *, allow_combined: bool) -> ReplySpec:
    """Ask which site a report/query belongs to, once its project is settled
    but the project has more than one site. ``sites`` is (site_id, name)
    pairs. Row id is "site_{site_id}", matched verbatim by the caller that
    resumes the pending report/query once one is tapped.

    ``allow_combined`` adds an "All Sites Combined" row -- only ever true for
    an inventory query (asking about stock can meaningfully span every site);
    a material report being recorded must always resolve to one real site,
    so recording never offers this option."""
    capacity = 9 if allow_combined else 10
    rows = [ListRow(f"site_{site_id}", name) for site_id, name in sites[:capacity]]
    if allow_combined:
        rows.append(ListRow(ALL_SITES_ROW_ID, "All Sites Combined"))
    text = (
        "Which site would you like — or everything combined?"
        if allow_combined
        else "Which site is this for?"
    )
    return ReplySpec(text=text, list_button_label="Choose site", list_rows=tuple(rows))


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


# WhatsApp message types Mesiri can't act on yet, mapped to what to call them
# when declining. Keyed by Meta's raw `type` (kept on NormalizedMessage.
# metadata["raw_type"]) rather than InputModality, because every one of these
# normalizes to the same UNKNOWN modality -- the raw type is the only thing
# left that can make the reply specific.
_UNSUPPORTED_TYPE_LABELS: dict[str, str] = {
    "document": "documents or PDFs",
    "video": "videos",
    "sticker": "stickers",
    "location": "location pins",
    "contacts": "shared contacts",
    # A voice note normalizes to VOICE and never reaches here; a music/audio
    # file (audio.voice falsy) does.
    "audio": "audio files",
}

# Not user-authored content, so declining would be noise rather than help:
# a reaction is an emoji tap on one of Mesiri's own replies (answering every
# 👍 with "I can't handle this" would be maddening), and `system` is Meta's
# own notice (e.g. the sender changed their number). Both are dropped
# quietly -- still logged, just not replied to.
SILENTLY_IGNORED_RAW_TYPES: frozenset[str] = frozenset({"reaction", "system", "order"})


def render_unsupported_media_reply(raw_type: str | None) -> str:
    """Tell the sender their message arrived but can't be acted on yet.

    Silence is the one outcome that must never happen here: a field worker
    who gets no answer can't tell "Mesiri ignored my PDF" from "Mesiri is
    down", so they either resend or assume the report landed when it didn't.
    Always names a concrete way to get the same information in -- a decline
    that doesn't say what to do instead just moves the dead end.

    Callers must check SILENTLY_IGNORED_RAW_TYPES first; this always returns
    a reply.
    """
    label = _UNSUPPORTED_TYPE_LABELS.get(str(raw_type or ""), "this kind of message")
    return (
        f"📎 Got your message — but I can't read {label} yet.\n\n"
        "Send it one of these ways instead:\n"
        "  • 📷 A photo (of a bill, delivery note, or the site)\n"
        "  • 🎤 A voice note\n"
        "  • ⌨️ Or just type it out"
    )


def render_material_create_offer(name: str) -> ReplySpec:
    """The reported material isn't in the catalog and the sender's role is
    allowed to add one (see the org's whatsapp_material_create_roles setting)
    -- offer to add it inline instead of dead-ending the report the way
    render_material_not_found_reply does. Row ids "matnew_yes"/"matnew_no",
    matched verbatim by resume_pending_report_with_material_create."""
    return ReplySpec(
        text=(
            f'"{name}" isn\'t in your materials catalog yet.\n\n'
            "Add it and continue with this report?"
        ),
        buttons=(ListRow("matnew_yes", "Yes, add it"), ListRow("matnew_no", "No")),
    )


def render_material_create_unit_picker(name: str, units: list[tuple[str, str]]) -> ReplySpec:
    """Adding `name` to the catalog needs a Stock Unit and the report's own
    text didn't carry a recognizable one. Row ids "matunit_{unit_id}",
    matched verbatim by resume_pending_report_with_material_unit_choice.

    A material's Stock Unit is fixed for its lifetime in V1 (no unit
    conversion), so this is asked once, up front, rather than inferred and
    silently locked in."""
    rows = tuple(ListRow(f"matunit_{unit_id}", display) for unit_id, display in units[:10])
    return ReplySpec(
        text=f"What unit is {name} measured in?",
        list_button_label="Choose unit",
        list_rows=rows,
    )


def render_material_create_declined_reply(name: str) -> str:
    """The sender declined to add the material. Nudge toward a spelling
    mistake rather than just closing: a near-miss name ("Fevikol" vs
    "Fevicol") is the most likely reason a real material didn't match, and
    adding it under the wrong spelling would fragment the catalog."""
    return (
        f'Ok — "{name}" wasn\'t added.\n\n'
        "If it was a spelling mistake, resend the report with the correct name."
    )


def render_material_created_reply(name: str, unit_display: str) -> str:
    """Confirms the catalog entry before the held report resumes, so the
    unit the material is now permanently tracked in is stated explicitly
    rather than only showing up later in the confirmation's field list."""
    return f"✅ Added {name} to your catalog, tracked in {unit_display}."


def render_material_not_found_reply(name: str) -> str:
    """No catalog material matched at all and the org's catalog is empty --
    distinct from the picker case for the same reason render_no_projects_reply
    is: tapping won't help, there's nothing to choose from."""
    return f'I couldn\'t find "{name}" in the materials catalog. Ask your admin to add it first.'


def render_usage_exceeds_stock_reply(
    *, material_name: str, unit: str, requested: float, available: float
) -> ReplySpec:
    """A usage report's quantity exceeds what's actually in stock -- block it
    instead of the old cosmetic-only confirmation warning (workflows/material
    /nodes.py's _low_stock_warning let the user tap Yes anyway and stock went
    negative, the real-world bug this fixes). Row ids "stock_cap"/
    "stock_arrival"/"stock_cancel", matched verbatim by
    resume_pending_report_with_stock_choice."""
    return ReplySpec(
        text=(
            f"⚠️ You reported using {requested:g} {unit} of {material_name}, but "
            f"only {available:g} {unit} is in stock — that's not possible.\n\n"
            "What would you like to do?"
        ),
        buttons=(
            ListRow("stock_cap", "Cap at available"),
            ListRow("stock_arrival", "It's an arrival"),
            ListRow("stock_cancel", "Cancel"),
        ),
    )


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
