"""Pure structural validation for CreateProjectCommand — no DB, no I/O.

Duplicate-name checks are deliberately not here -- projects have no
uniqueness constraint on name (matching the REST create_project endpoint's
behaviour), so there is nothing to resolve against the DB.

Role enforcement lives here too, mirroring application/finance/validation.py's
docstring reasoning exactly: this is defense-in-depth, not the only gate --
runtime/inbound_journey.py already refuses to even start the workflow for a
disallowed role. This check exists in case that gate is ever bypassed or a
future caller reaches this Command directly.
"""

from __future__ import annotations

from .create_commands import CreateProjectCommand

# Matches apps/whatsapp-assistant/src/projects/router.py's _CREATE_ROLES
# exactly -- the same roles that may create a Project over REST may create
# one over WhatsApp.
_PROJECT_CREATE_ROLES = frozenset({"ADMIN", "PROJECT_MANAGER"})


def validate(cmd: CreateProjectCommand) -> list[str]:
    reasons: list[str] = []
    if str(cmd.created_by_role or "").strip().upper() not in _PROJECT_CREATE_ROLES:
        reasons.append("only an admin or project manager can create a project")
    if not (cmd.name or "").strip():
        reasons.append("project name is required")
    return reasons
