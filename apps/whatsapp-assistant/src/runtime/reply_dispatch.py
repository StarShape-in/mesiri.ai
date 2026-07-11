"""Shared ReplySpec -> transport dispatch, used by both the main journey
(runtime/inbound_journey.py) and any fast-path handler that renders its own
ReplySpec outside the journey (e.g. the project-selection resume in
runtime/dependencies.py). One place decides send_text vs send_list vs
send_button so the two call sites can't drift."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from channel.replies import ListRow, ReplySpec


async def send_reply_spec(
    reply: ReplySpec,
    wa_id: str,
    *,
    send_text: Callable[[str, str], Awaitable[Any]],
    send_list: Callable[[str, str, str, tuple[ListRow, ...]], Awaitable[Any]] | None = None,
    send_button: Callable[[str, str, tuple[ListRow, ...]], Awaitable[Any]] | None = None,
) -> None:
    if reply.buttons and send_button is not None:
        await send_button(wa_id, body=reply.text, buttons=reply.buttons)
    elif reply.buttons:
        options = " / ".join(row.title for row in reply.buttons)
        await send_text(wa_id, f"{reply.text}\n\nReply {options}")
    elif reply.list_rows and send_list is not None:
        await send_list(
            wa_id,
            body=reply.text,
            button_label=reply.list_button_label or "Choose one",
            rows=reply.list_rows,
        )
    elif reply.list_rows:
        options = "\n".join(f"  • {row.title}" for row in reply.list_rows)
        await send_text(wa_id, f"{reply.text}\n{options}")
    else:
        await send_text(wa_id, reply.text)
