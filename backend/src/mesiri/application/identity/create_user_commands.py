"""CreateUser Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/projects/add_member_commands.py's AddProjectMemberCommand
reasoning. Unlike that command, there is no project_id to carry -- a new
user isn't created under any project (see workflows/create_user/nodes.py's
docstring); assigning them to one is a separate, later ADD_PROJECT_MEMBER.
"""

from __future__ import annotations

from pydantic import BaseModel


class CreateUserCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None
    full_name: str
    whatsapp_number: str
    role: str = "SITE_ENGINEER"

    correlation_id: str | None = None
