"""CreateProjectCommand validation — unit tests (pure, no DB, no I/O)."""

from __future__ import annotations

from mesiri.application.projects.create_commands import CreateProjectCommand
from mesiri.application.projects.create_validation import validate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> CreateProjectCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        name="Skyline Towers",
    )
    base.update(overrides)
    return CreateProjectCommand(**base)


def test_admin_role_has_no_role_reason():
    assert validate(_command(created_by_role="ADMIN")) == []


def test_project_manager_role_has_no_role_reason():
    assert validate(_command(created_by_role="PROJECT_MANAGER")) == []


def test_site_engineer_role_is_rejected():
    reasons = validate(_command(created_by_role="SITE_ENGINEER"))
    assert "only an admin or project manager can create a project" in reasons


def test_missing_role_is_rejected():
    """A None/blank role must fail closed, not be treated as allowed."""
    assert "only an admin or project manager can create a project" in validate(
        _command(created_by_role=None)
    )


def test_role_check_is_case_insensitive():
    assert validate(_command(created_by_role="admin")) == []


def test_create_with_name_has_no_reasons():
    assert validate(_command(name="Skyline Towers")) == []


def test_create_without_name_is_rejected():
    assert "project name is required" in validate(_command(name=""))
    assert "project name is required" in validate(_command(name="   "))
