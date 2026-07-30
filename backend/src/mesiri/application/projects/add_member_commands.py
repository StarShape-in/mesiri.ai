"""AddProjectMember Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
create_site_commands.py's CreateSiteCommand reasoning. `project_id` is
resolved by the WhatsApp context pipeline before this command is ever built
(see workflows/add_project_member/nodes.py's docstring) -- unlike
member_name/role, it is never a candidate field extracted from the message
text. `member_user_id` starts unset and is filled in by the Handler (see
handlers.py) after resolving `member_name` against the org's real users --
never set by the mapper, since that resolution is a DB round trip a pure
mapper must not perform.
"""

from __future__ import annotations

from pydantic import BaseModel


class AddProjectMemberCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    project_id: str
    created_by: str
    created_by_role: str | None = None
    member_name: str
    member_user_id: str | None = None
    role: str = "SITE_ENGINEER"

    correlation_id: str | None = None
