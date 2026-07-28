"""CreateProject Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/finance/commands.py's ManageMoneyAccountCommand reasoning:
backend is imported in-process by apps/whatsapp-assistant, so this command
doesn't need to live in shared/contracts for the WhatsApp path to reach it.
The dashboard's own Project creation goes through a separate REST endpoint
(apps/whatsapp-assistant/src/projects/router.py's create_project) that
writes directly, with no draft/confirm step -- this command exists only for
the confirmed-message (WhatsApp) path, which architecture rule #4 requires
to go through draft/confirm before anything is persisted.
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateProjectCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None
    name: str
    location: str | None = None
    client: str | None = None
    description: str | None = None

    correlation_id: str | None = None
