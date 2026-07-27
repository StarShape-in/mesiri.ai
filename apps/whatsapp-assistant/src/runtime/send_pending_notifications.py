"""Drains and sends #9 Notifications' queued 'pending' rows over WhatsApp.

Invocable manually or via a cron entry -- not a persistent worker, same
convention as backend/src/mesiri/scripts/run_notification_checks.py (which
queues the rows this script sends) and project_timeline_events.py. This is
deliberately a SEPARATE process/script from the backend check, not the same
one: the backend must never talk to Meta's Cloud API directly (architecture
boundary -- only this app holds WhatsApp credentials and the WhatsAppSender
adapter).

For each pending row: resolve the recipient's wa_id, check quiet hours and
the WhatsApp 24h session window (application/notifications/checks.py, in
the backend package -- pure logic, safe to import from either side), and
either send or skip with a recorded reason. Never sends silently outside
the session window: Meta rejects a free-form send there, and pretending
otherwise would be worse than skipping honestly.

Recommended VPS crontab entry (ops-managed, not tracked in this repo):
    */15 * * * * cd /opt/mesiri/apps/whatsapp-assistant/src && \
        PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src \
        /opt/mesiri/.venv/bin/python -m runtime.send_pending_notifications \
        >> /var/log/mesiri/notification-sender.log 2>&1

Run:  python -m runtime.send_pending_notifications
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

_RULE_KEY_MESSAGES: dict[str, str] = {
    "stuck_confirmation": (
        "⏳ You have a report waiting for your YES/NO reply — "
        "just reply to it to continue, or CANCEL to discard it."
    ),
}


def _render(rule_key: str) -> str:
    return _RULE_KEY_MESSAGES.get(
        rule_key, "You have a pending item that needs your attention."
    )


async def run() -> dict[str, int]:
    import httpx

    from backend.postgres.actor import PostgresActorReader
    from channel.whatsapp.outbound import WhatsAppSender
    from mesiri.application.notifications.checks import (
        is_quiet_hours,
        is_within_whatsapp_session_window,
    )
    from mesiri.bootstrap.settings import Settings as BackendSettings
    from mesiri.infrastructure.postgres.database import PostgresDatabase
    from runtime.dependencies import Settings as WhatsAppSettings
    from runtime.notification_query import NotificationSendQueueService

    whatsapp_settings = WhatsAppSettings()  # type: ignore[call-arg]
    backend_settings = BackendSettings()
    db = PostgresDatabase(backend_settings.postgres)
    await db.connect()

    counts = {"sent": 0, "skipped": 0}
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            sender = WhatsAppSender(
                client=http_client,
                access_token=whatsapp_settings.access_token,
                phone_number_id=whatsapp_settings.phone_number_id,
                api_version=whatsapp_settings.api_version,
                graph_base_url=whatsapp_settings.graph_base_url,
            )
            actor_reader = PostgresActorReader()
            queue = NotificationSendQueueService(db, actor_reader)

            pending = await queue.list_pending()
            for row in pending:
                notification_id = str(row["id"])
                wa_id = await queue.resolve_recipient_wa_id(
                    str(row["recipient_user_id"]) if row.get("recipient_user_id") else None
                )
                if wa_id is None:
                    await queue.mark_skipped(
                        notification_id=notification_id, reason="no_resolvable_recipient"
                    )
                    counts["skipped"] += 1
                    continue

                last_inbound = await queue.last_inbound_at(wa_id)
                now = datetime.now(tz=UTC)
                if not is_within_whatsapp_session_window(last_inbound_at=last_inbound, now=now):
                    # Outside Meta's free-form window -- sending would be
                    # silently rejected. An approved message template would
                    # be required instead; registering one with Meta is an
                    # ops action this script cannot do on its own.
                    await queue.mark_skipped(
                        notification_id=notification_id,
                        reason="outside_whatsapp_session_window_needs_template",
                    )
                    counts["skipped"] += 1
                    continue

                if is_quiet_hours(local_now=now):
                    # Left 'pending' on purpose -- not skipped -- so the
                    # next drain (within 15 min, per the recommended cron
                    # cadence) picks it back up once quiet hours end,
                    # rather than losing it.
                    continue

                sent = await sender.send_text(wa_id, _render(row["rule_key"]))
                if sent:
                    await queue.mark_sent(notification_id=notification_id)
                    counts["sent"] += 1
                else:
                    await queue.mark_skipped(notification_id=notification_id, reason="send_failed")
                    counts["skipped"] += 1
    finally:
        await db.disconnect()

    return counts


def main() -> int:
    counts = asyncio.run(run())
    print(f"notification-sender: sent {counts['sent']}, skipped {counts['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
