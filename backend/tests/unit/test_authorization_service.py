"""Unit tests for AuthorizationService.

These tests use a fake/mock database connection to verify authorization
logic without requiring live PostgreSQL.

Project/site scope now comes from project_members/site_members (+ an
org-wide role bypass), not users.access_policy -- see the project/site
membership audit. access_policy is still parsed for GET /me backward
compatibility but is no longer authoritative, so it's irrelevant to scope
assertions below; role and the mocked project_members/site_members query
results are what drive project_scope/site_scopes now.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from mesiri.authorization.service import AuthorizationService


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    return AsyncMock()


@pytest.fixture
def sample_user_row():
    """Create a sample user database row. role='member' (non-org-wide) by
    default so most tests exercise the project_members-driven path rather
    than the ADMIN bypass -- override role explicitly for bypass tests."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    row = MagicMock()
    row.id = user_id
    row.organization_id = org_id
    row.role = "member"
    row.status = "active"
    row.access_policy = None

    return row


def _result(rows: list) -> MagicMock:
    result_mock = MagicMock()
    result_mock.fetchall.return_value = rows
    return result_mock


def _member_row(project_id, site_access_mode="all_sites"):
    row = MagicMock()
    row.project_id = project_id
    row.site_access_mode = site_access_mode
    return row


async def test_resolve_from_jwt_admin_role_grants_all_projects(mock_conn, sample_user_row):
    """An org-wide role (ADMIN) bypasses project_members entirely -- the
    SQL-native equivalent of the old access_policy 'all_projects' mode."""
    sample_user_row.role = "admin"
    all_org_projects = [uuid.uuid4(), uuid.uuid4()]

    mock_conn.execute.side_effect = [
        _result([sample_user_row]),  # user lookup
        _result([MagicMock(id=pid) for pid in all_org_projects]),  # site_scopes: all org projects
    ]

    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )

    assert ctx.user_id == sample_user_row.id
    assert ctx.organization_id == sample_user_row.organization_id
    assert ctx.role == sample_user_row.role
    assert ctx.status == "active"
    assert ctx.is_active is True
    assert ctx.project_scope.grants_all_org_projects is True
    # Site scope is resolved for every org project, all_sites each.
    for pid in all_org_projects:
        assert ctx.site_scope_for_project(pid).grants_all_sites is True


async def test_resolve_from_jwt_user_not_found(mock_conn):
    """Test 401 when user not found in database."""
    mock_conn.execute.return_value = _result([])

    service = AuthorizationService(mock_conn)

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_from_jwt(
            user_id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            role="admin",
        )

    assert exc_info.value.status_code == 401
    assert "not found" in exc_info.value.detail.lower()


async def test_resolve_from_jwt_org_mismatch(mock_conn, sample_user_row):
    """Test 401 when JWT org doesn't match user's org in database."""
    mock_conn.execute.return_value = _result([sample_user_row])

    service = AuthorizationService(mock_conn)

    different_org = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_from_jwt(
            user_id=sample_user_row.id,
            org_id=different_org,  # Different from user's org
            role=sample_user_row.role,
        )

    assert exc_info.value.status_code == 401
    assert "organization" in exc_info.value.detail.lower()


async def test_resolve_from_jwt_suspended_user(mock_conn, sample_user_row):
    """Test 401 when user status is suspended."""
    sample_user_row.status = "suspended"
    mock_conn.execute.return_value = _result([sample_user_row])

    service = AuthorizationService(mock_conn)

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_from_jwt(
            user_id=sample_user_row.id,
            org_id=sample_user_row.organization_id,
            role=sample_user_row.role,
        )

    assert exc_info.value.status_code == 401
    assert "suspended" in exc_info.value.detail.lower()


async def test_resolve_from_jwt_inactive_user(mock_conn, sample_user_row):
    """Test 401 when user status is inactive."""
    sample_user_row.status = "inactive"
    mock_conn.execute.return_value = _result([sample_user_row])

    service = AuthorizationService(mock_conn)

    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_from_jwt(
            user_id=sample_user_row.id,
            org_id=sample_user_row.organization_id,
            role=sample_user_row.role,
        )

    assert exc_info.value.status_code == 401


async def test_resolve_from_jwt_custom_projects_scope(mock_conn, sample_user_row):
    """A non-org-wide role's access is exactly its project_members rows."""
    project_id_1 = uuid.uuid4()
    project_id_2 = uuid.uuid4()

    mock_conn.execute.side_effect = [
        _result([sample_user_row]),  # user lookup
        _result([MagicMock(project_id=project_id_1), MagicMock(project_id=project_id_2)]),  # project_members
        _result([_member_row(project_id_1), _member_row(project_id_2)]),  # site_access_mode per project
    ]

    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )

    assert ctx.project_scope.grants_all_org_projects is False
    assert len(ctx.project_scope.project_ids) == 2
    assert project_id_1 in ctx.project_scope.project_ids
    assert project_id_2 in ctx.project_scope.project_ids
    assert ctx.site_scope_for_project(project_id_1).grants_all_sites is True


async def test_resolve_from_jwt_no_membership_rows_denies_by_default(mock_conn, sample_user_row):
    """No project_members rows for this user -> zero projects (deny-by-default,
    same contract the old empty custom_projects list used to guarantee)."""
    mock_conn.execute.side_effect = [
        _result([sample_user_row]),  # user lookup
        _result([]),  # no project_members rows
    ]

    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )

    assert ctx.project_scope.grants_all_org_projects is False
    assert ctx.project_scope.grants_no_projects is True
    assert len(ctx.project_scope.project_ids) == 0
    # No projects means _resolve_site_scopes short-circuits without a query.
    assert mock_conn.execute.call_count == 2


async def test_resolve_from_jwt_custom_sites_scope(mock_conn, sample_user_row):
    """A project_members row with site_access_mode='custom_sites' is
    narrowed further by the matching site_members rows."""
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()

    mock_conn.execute.side_effect = [
        _result([sample_user_row]),  # user lookup
        _result([MagicMock(project_id=project_id)]),  # project_members
        _result([_member_row(project_id, site_access_mode="custom_sites")]),  # site_access_mode
        _result([MagicMock(project_id=project_id, site_id=site_id)]),  # site_members
    ]

    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )

    site_scope = ctx.site_scope_for_project(project_id)
    assert site_scope.grants_all_sites is False
    assert site_scope.site_ids == {site_id}


async def test_resolve_from_jwt_unresolved_project_denies_site_access_by_default(
    mock_conn, sample_user_row
):
    """site_scope_for_project for a project the user has no access to at all
    (not even in project_scope) must deny by default, not raise a KeyError."""
    mock_conn.execute.side_effect = [
        _result([sample_user_row]),  # user lookup
        _result([]),  # no project_members rows
    ]

    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )

    scope = ctx.site_scope_for_project(uuid.uuid4())
    assert scope.grants_no_sites is True


def test_resolve_site_scope_static_delegates_to_context_helper():
    """AuthorizationService._resolve_site_scope is a legacy pure-JSON helper,
    kept for GET /me's informational access_policy field -- not used by
    scope resolution anymore, but still a correct standalone function."""
    from mesiri.authorization.context import AccessPolicy

    project_id = uuid.uuid4()
    policy = AccessPolicy(mode="all_projects", projects=[])

    scope = AuthorizationService._resolve_site_scope(policy, project_id)

    assert scope.grants_all_sites is True
