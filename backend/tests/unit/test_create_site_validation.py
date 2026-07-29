"""CreateSiteCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from mesiri.application.projects.create_site_commands import CreateSiteCommand
from mesiri.application.projects.create_site_validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> CreateSiteCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        project_id=PROJ,
        created_by=USR,
        created_by_role="ADMIN",
        name="Block A",
    )
    base.update(overrides)
    return CreateSiteCommand(**base)


def test_admin_role_has_no_role_reason():
    assert validate(_command(created_by_role="ADMIN")) == []


def test_project_manager_role_has_no_role_reason():
    assert validate(_command(created_by_role="PROJECT_MANAGER")) == []


def test_site_engineer_role_is_rejected():
    reasons = validate(_command(created_by_role="SITE_ENGINEER"))
    assert "only an admin or project manager can create a site" in reasons


def test_missing_role_is_rejected():
    assert "only an admin or project manager can create a site" in validate(
        _command(created_by_role=None)
    )


def test_create_with_name_and_project_has_no_reasons():
    assert validate(_command()) == []


def test_create_without_name_is_rejected():
    assert "site name is required" in validate(_command(name=""))
    assert "site name is required" in validate(_command(name="   "))


def test_create_without_project_id_is_rejected():
    assert "a project is required to create a site" in validate(_command(project_id=""))
    assert "a project is required to create a site" in validate(_command(project_id="   "))
