"""Unit tests for AuthorizationService.

These tests use a fake/mock database connection to verify authorization
logic without requiring live PostgreSQL.
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
    """Create a sample user database row."""
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    
    row = MagicMock()
    row.id = user_id
    row.organization_id = org_id
    row.role = "admin"
    row.status = "active"
    row.access_policy = {"mode": "all_projects", "projects": []}
    
    return row


async def test_resolve_from_jwt_success(mock_conn, sample_user_row):
    """Test successful authorization context resolution."""
    # Setup mock to return user
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
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


async def test_resolve_from_jwt_user_not_found(mock_conn):
    """Test 401 when user not found in database."""
    # Setup mock to return no user
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = []
    mock_conn.execute.return_value = result_mock
    
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
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
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
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
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
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
    service = AuthorizationService(mock_conn)
    
    with pytest.raises(HTTPException) as exc_info:
        await service.resolve_from_jwt(
            user_id=sample_user_row.id,
            org_id=sample_user_row.organization_id,
            role=sample_user_row.role,
        )
    
    assert exc_info.value.status_code == 401


async def test_resolve_from_jwt_custom_projects_scope(mock_conn, sample_user_row):
    """Test custom_projects scope resolution."""
    project_id_1 = str(uuid.uuid4())
    project_id_2 = str(uuid.uuid4())
    
    sample_user_row.access_policy = {
        "mode": "custom_projects",
        "projects": [
            {"projectId": project_id_1, "siteAccess": {"mode": "all_sites"}},
            {"projectId": project_id_2, "siteAccess": {"mode": "all_sites"}},
        ]
    }
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )
    
    assert ctx.project_scope.grants_all_org_projects is False
    assert len(ctx.project_scope.project_ids) == 2
    assert uuid.UUID(project_id_1) in ctx.project_scope.project_ids
    assert uuid.UUID(project_id_2) in ctx.project_scope.project_ids


async def test_resolve_from_jwt_empty_custom_projects(mock_conn, sample_user_row):
    """Test empty custom_projects scope grants no access."""
    sample_user_row.access_policy = {
        "mode": "custom_projects",
        "projects": []
    }
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )
    
    assert ctx.project_scope.grants_all_org_projects is False
    assert ctx.project_scope.grants_no_projects is True
    assert len(ctx.project_scope.project_ids) == 0


async def test_resolve_from_jwt_null_policy_denies_by_default(mock_conn, sample_user_row):
    """Test null access policy defaults to empty custom (deny by default)."""
    sample_user_row.access_policy = None
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )
    
    assert ctx.project_scope.grants_no_projects is True


async def test_resolve_from_jwt_malformed_policy_denies_by_default(mock_conn, sample_user_row):
    """Test malformed policy defaults to empty custom (deny by default)."""
    sample_user_row.access_policy = {
        "mode": "invalid_mode",
        "projects": []
    }
    
    result_mock = AsyncMock()
    result_mock.fetchall.return_value = [sample_user_row]
    mock_conn.execute.return_value = result_mock
    
    service = AuthorizationService(mock_conn)
    ctx = await service.resolve_from_jwt(
        user_id=sample_user_row.id,
        org_id=sample_user_row.organization_id,
        role=sample_user_row.role,
    )
    
    assert ctx.project_scope.grants_no_projects is True
