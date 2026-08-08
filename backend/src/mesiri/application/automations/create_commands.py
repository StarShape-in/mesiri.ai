"""CreateAutomation Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/projects/create_site_commands.py's CreateSiteCommand reasoning.
Carries the same shape the REST `AutomationRequest`
(domains/automations/router.py) accepts, so both write paths -- the
dashboard's direct POST and this WhatsApp confirmed-command path -- end up
validated the same way and persisted through the same
PostgresAutomationRepository.create().
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateAutomationCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None
    project_id: str | None = None
    site_id: str | None = None
    action: str
    audience: str
    audience_user_ids: list[str] | None = None
    # Best-effort person-name hints (USERS only), as stated in chat -- e.g.
    # "ask Ilan or Hysam" -> ["Ilan", "Hysam"]. Resolved against the org's
    # real active users by name_resolution.py before persist; never used
    # directly as a recipient id. Absent once audience_user_ids is already
    # populated (the dashboard's direct-id REST path never sets this).
    audience_names: list[str] | None = None
    audience_role: str | None = None
    message: str | None = None
    frequency: str = "DAILY"
    day_of_week: int | None = None
    time_of_day: str
    timezone: str = "UTC"

    correlation_id: str | None = None
