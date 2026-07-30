"""Has this WhatsApp number ever messaged us before?

Answers the one question ``channel/replies.py``'s ``is_first_message`` needs.
That flag has existed since the greeting menu was written -- with the intro
copy already drafted behind it -- but nothing ever set it, so every user's
first-ever message got the returning-user greeting ("What are you reporting
today?") and nobody was ever told what Mesiri is.

Reads ``inbound_messages``, which ``backend/postgres/message_logger.py``
writes at receipt time. Ordering matters and is safe: ``log_received`` runs
at the top of the journey (message_journey.py, well before any greeting is
rendered), so the current message is *already* a row by the time this is
called. "First ever" therefore means "no row for this sender other than this
one", not "no rows at all" -- checking for zero rows would never be true and
the intro would never show.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

_log = logging.getLogger(__name__)


class FirstMessageQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def is_first_message(self, *, sender_wa_id: str, correlation_id: str) -> bool:
        """True when this is the sender's very first inbound message.

        Best-effort: any failure returns False, which renders the shorter
        returning-user greeting. Getting this wrong in that direction costs
        a first-time user one paragraph of introduction; getting it wrong
        the other way re-introduces Mesiri to someone who has used it for
        months, on every "hi". False is the safe default.
        """
        from sqlalchemy import text

        try:
            async with self._db.transaction() as conn:
                result = await conn.execute(
                    text(
                        "SELECT 1 FROM inbound_messages "
                        "WHERE sender_wa_id = :sender_wa_id "
                        "AND correlation_id <> :correlation_id "
                        "LIMIT 1"
                    ),
                    {"sender_wa_id": sender_wa_id, "correlation_id": correlation_id},
                )
                return result.first() is None
        except Exception:  # noqa: BLE001 -- a greeting is never worth failing a reply over
            _log.warning(
                "first_message_query.failed correlation_id=%s", correlation_id, exc_info=True
            )
            return False
