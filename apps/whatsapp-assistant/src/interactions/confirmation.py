"""Confirmation message rendering — formats the outbound 'please confirm' prompt.

The workflow graph computes a human-readable summary of the action it wants to
perform and stores it as ``pending_prompt`` in WorkflowStateV2. This module
wraps that text in a consistent WhatsApp-friendly envelope with reply
instructions.

Kept deliberately simple in M7. Future work: rich WhatsApp interactive message
templates (buttons, lists) via the channel/ module.
"""

from __future__ import annotations

_REPLY_INSTRUCTIONS = "\n\nReply *YES* to confirm, *NO* to discard, or *CANCEL* to abort."


def format_confirmation_message(pending_prompt: str) -> str:
    """Wrap a workflow's pending_prompt with standard reply instructions.

    Call this when building the initial outbound confirmation request. Do NOT
    call it again when re-showing a blocked prompt — the instructions are
    already embedded in the stored pending_prompt.
    """
    return pending_prompt.strip() + _REPLY_INSTRUCTIONS
