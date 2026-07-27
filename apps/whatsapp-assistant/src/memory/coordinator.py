"""Write side of conversation memory: update scopes after a turn completes.

Read side is context_loader.py. Kept as a separate module because the two
have different call sites -- load happens once, early, before understanding;
update happens once, late, after a reply is decided -- and different failure
tolerance is fine for both (both are best-effort).
"""

from __future__ import annotations

import logging

from .conversation_scope import CurrentActivityStore, CurrentDateStore
from .recent_turns import ConversationTurn, RecentTurnsStore

logger = logging.getLogger(__name__)


class ConversationMemoryCoordinator:
    """Updates conversation-memory scopes once a turn's outcome is known.

    Every method is independently best-effort (caught and logged, never
    raised) -- memory bookkeeping must never be the reason a reply fails to
    send. Callers should fire these without awaiting the pipeline's own
    critical path where possible (see runtime/inbound_journey.py's existing
    `_safe()`/`asyncio.ensure_future` conventions for logging calls of the
    same shape).
    """

    def __init__(
        self,
        *,
        current_activity: CurrentActivityStore,
        current_date: CurrentDateStore,
        recent_turns: RecentTurnsStore,
    ) -> None:
        self._current_activity = current_activity
        self._current_date = current_date
        self._recent_turns = recent_turns

    async def record_turn(
        self, *, user_id: str, user_text: str, assistant_reply: str, correlation_id: str
    ) -> None:
        if not user_text and not assistant_reply:
            return
        try:
            await self._recent_turns.append(
                user_id=user_id,
                turn=ConversationTurn(
                    user_text=user_text,
                    assistant_reply=assistant_reply,
                    correlation_id=correlation_id,
                ),
            )
        except Exception:  # noqa: BLE001
            logger.warning("memory.record_turn_failed user=%s", user_id, exc_info=True)

    async def record_activity(self, *, user_id: str, activity_id: str) -> None:
        """Call when a CREATE_ACTIVITY or ADD_PROGRESS_UPDATE draft is
        confirmed -- see workflows/site_update/nodes.py and
        workflows/activity_continuation/nodes.py for where activity_id comes
        from. This is what lets the *next* continuation message in the same
        conversation prefer this activity over runtime.activity_query's
        site-wide "most recently updated" guess."""
        try:
            await self._current_activity.set_current(user_id=user_id, activity_id=activity_id)
        except Exception:  # noqa: BLE001
            logger.warning("memory.record_activity_failed user=%s", user_id, exc_info=True)

    async def record_explicit_date(self, *, user_id: str, occurred_date: str) -> None:
        """Call only when occurred_date_source (see canonicalization/
        occurred_date.py) marks the date as user-stated, never inferred --
        an inferred default must not be remembered as if the user said it."""
        try:
            await self._current_date.set_current(user_id=user_id, occurred_date=occurred_date)
        except Exception:  # noqa: BLE001
            logger.warning("memory.record_date_failed user=%s", user_id, exc_info=True)
