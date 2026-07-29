"""Pure structural validation for CreateSiteCommand — no DB, no I/O.

The target project's existence is checked at persist time (a DB round trip,
mirroring create_execution.py's defense-in-depth-only checks elsewhere) --
this file only rejects a command that's structurally incomplete before it
ever reaches the repository.

Role enforcement lives here too, mirroring create_validation.py's docstring
reasoning exactly: this is defense-in-depth, not the only gate --
runtime/inbound_journey.py already refuses to even start the workflow for a
disallowed role.
"""

from __future__ import annotations

from .create_site_commands import CreateSiteCommand

# Matches create_validation.py's _PROJECT_CREATE_ROLES exactly -- the same
# roles that may create a Project may add a Site under one.
_SITE_CREATE_ROLES = frozenset({"ADMIN", "PROJECT_MANAGER"})


def validate(cmd: CreateSiteCommand) -> list[str]:
    reasons: list[str] = []
    if str(cmd.created_by_role or "").strip().upper() not in _SITE_CREATE_ROLES:
        reasons.append("only an admin or project manager can create a site")
    if not (cmd.project_id or "").strip():
        reasons.append("a project is required to create a site")
    if not (cmd.name or "").strip():
        reasons.append("site name is required")
    return reasons
