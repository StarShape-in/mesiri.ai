"""Deterministic (non-AI) parser for account-admin WhatsApp commands.

Pure -- no I/O. Recognizes a small fixed set of imperative phrasings for
create/rename/deactivate; anything else returns None so the caller falls
through to the normal AI-understood journey. Intentionally narrow (regex,
not NLU): these are ADMIN/FINANCE-only, low-volume commands where a
predictable syntax is preferable to an LLM guess for something that mutates
the chart of accounts (see runtime/account_admin_journey.py for the role
gate and workflow handoff).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CREATE_RE = re.compile(r"^create\s+account\s+(.+)$", re.IGNORECASE)
_RENAME_RE = re.compile(r"^rename\s+(.+?)\s+to\s+(.+)$", re.IGNORECASE)
_DEACTIVATE_RE = re.compile(r"^deactivate\s+(?:account\s+)?(.+)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedAccountAdminCommand:
    action: str
    fields: dict[str, str]


def parse_account_admin_command(text: str) -> ParsedAccountAdminCommand | None:
    """Order matters: rename/deactivate are checked before create would ever
    be relevant, but none of the three phrasings overlap in practice."""
    stripped = text.strip()
    if not stripped:
        return None

    match = _RENAME_RE.match(stripped)
    if match:
        target, new_name = match.group(1).strip(), match.group(2).strip()
        if target and new_name:
            return ParsedAccountAdminCommand(
                action="rename",
                fields={"action": "rename", "target_name": target, "new_name": new_name},
            )

    match = _DEACTIVATE_RE.match(stripped)
    if match:
        target = match.group(1).strip()
        if target:
            return ParsedAccountAdminCommand(
                action="deactivate", fields={"action": "deactivate", "target_name": target}
            )

    match = _CREATE_RE.match(stripped)
    if match:
        name = match.group(1).strip()
        if name:
            return ParsedAccountAdminCommand(
                action="create", fields={"action": "create", "name": name, "account_type": "cash"}
            )

    return None
