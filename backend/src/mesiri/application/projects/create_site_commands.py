"""CreateSite Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
create_commands.py's CreateProjectCommand reasoning. `project_id` is
resolved by the WhatsApp context pipeline before this command is ever built
(see workflows/site_create/nodes.py's docstring) -- unlike name/location, it
is never a candidate field extracted from the message text.
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateSiteCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    project_id: str
    created_by: str
    created_by_role: str | None = None
    name: str
    location: str | None = None

    correlation_id: str | None = None
