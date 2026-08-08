"""Pure decision logic for #9 Notifications -- no I/O, no DB.

The at-most-once guarantee itself is enforced at the schema level (migration
0453's UNIQUE(organization_id, rule_key, subject_id, occurred_on) +
ON CONFLICT DO NOTHING in the repository), not here -- there is nothing to
unit test for "did we already send this", the database is the single source
of truth for that question.

What IS worth testing in isolation, because getting any of them wrong wakes
someone up at the wrong time or silently drops a real message, are the three
independent timing decisions below.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

# Defaults -- not yet configurable per-organization (a natural extension via
# the existing organization_settings key-value mechanism -- see
# apps/whatsapp-assistant/src/runtime/org_settings_query.py's
# whatsapp_material_create_roles for the established pattern to follow).
DEFAULT_QUIET_HOURS_START = time(21, 0)  # 9pm
DEFAULT_QUIET_HOURS_END = time(7, 0)  # 7am
DEFAULT_MISSING_DPR_CUTOFF = time(18, 0)  # 6pm
DEFAULT_NO_UPDATES_CUTOFF = time(18, 0)  # 6pm
DEFAULT_STUCK_CONFIRMATION_AFTER = timedelta(hours=4)
DEFAULT_UNRESOLVED_ISSUE_AFTER = timedelta(hours=24)

# Meta only allows a free-form outbound message within this long of the
# user's last inbound message; outside it, an approved message template is
# required. Verified against the WhatsApp Cloud API's documented rule.
WHATSAPP_SESSION_WINDOW = timedelta(hours=24)


def is_after_cutoff(*, local_now: datetime, cutoff: time) -> bool:
    """Has the site's local "check by" time passed yet -- e.g. don't nudge
    about a missing DPR at 2pm, the day isn't over."""
    return local_now.time() >= cutoff


def is_quiet_hours(
    *,
    local_now: datetime,
    start: time = DEFAULT_QUIET_HOURS_START,
    end: time = DEFAULT_QUIET_HOURS_END,
) -> bool:
    """Handles the overnight wraparound correctly (start > end, e.g.
    21:00 -> 07:00 spans midnight) -- a naive `start <= now < end` comparison
    would be wrong for exactly this, the common case for quiet hours."""
    now_t = local_now.time()
    if start <= end:
        return start <= now_t < end
    return now_t >= start or now_t < end


def next_sendable_time(
    *,
    local_now: datetime,
    quiet_start: time = DEFAULT_QUIET_HOURS_START,
    quiet_end: time = DEFAULT_QUIET_HOURS_END,
) -> datetime:
    """If ``local_now`` falls in quiet hours, the next moment they end
    (today or tomorrow, depending which side of midnight ``local_now`` is
    on). Otherwise ``local_now`` unchanged -- send now."""
    if not is_quiet_hours(local_now=local_now, start=quiet_start, end=quiet_end):
        return local_now
    end_today = local_now.replace(
        hour=quiet_end.hour, minute=quiet_end.minute, second=0, microsecond=0
    )
    if local_now.time() < quiet_end:
        # Early-morning tail of an overnight window (e.g. 02:00 within
        # 21:00 -> 07:00) -- quiet hours end LATER TODAY.
        return end_today
    # Evening head of an overnight window (e.g. 22:00) -- quiet hours end
    # tomorrow, not today (today's end_today has already passed).
    return end_today + timedelta(days=1)


def is_within_whatsapp_session_window(
    *, last_inbound_at: datetime | None, now: datetime
) -> bool:
    """Whether a free-form message can still be sent, or Meta requires an
    approved template instead. None (no inbound message on record at all)
    means outside the window -- fail closed, since a free-form send outside
    the real window is silently rejected by Meta with no user-visible
    failure otherwise."""
    if last_inbound_at is None:
        return False
    return (now - last_inbound_at) < WHATSAPP_SESSION_WINDOW
