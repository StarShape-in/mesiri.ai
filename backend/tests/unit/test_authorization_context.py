"""Unit tests for AuthorizationContext and related models."""

from __future__ import annotations

import uuid

import pytest

from mesiri.authorization.context import (
    AccessPolicy,
    AuthorizationContext,
    ProjectAccessScope,
)


class TestAccessPolicy:
    """Tests for AccessPolicy model and parsing."""
    
    def test_from_db_json_all_projects(self):
        """Test parsing all_projects policy."""
        policy_json = {
            "mode": "all_projects",
            "projects": []
        }
        policy = AccessPolicy.from_db_json(policy_json)
        
        assert policy.mode == "all_projects"
        assert policy.projects == []
    
    def test_from_db_json_custom_projects(self):
        """Test parsing custom_projects policy with explicit grants."""
        project_id = str(uuid.uuid4())
        policy_json = {
            "mode": "custom_projects",
            "projects": [
                {
                    "projectId": project_id,
                    "siteAccess": {
                        "mode": "all_sites",
                        "siteIds": []
                    }
                }
            ]
        }
        policy = AccessPolicy.from_db_json(policy_json)
        
        assert policy.mode == "custom_projects"
        assert len(policy.projects) == 1
        assert policy.projects[0]["projectId"] == project_id
    
    def test_from_db_json_null_defaults_to_empty_custom(self):
        """Test that null policy defaults to empty custom (deny by default)."""
        policy = AccessPolicy.from_db_json(None)
        
        assert policy.mode == "custom_projects"
        assert policy.projects == []
    
    def test_from_db_json_unsupported_mode_defaults_to_empty_custom(self):
        """Test that unsupported mode defaults to empty custom (deny by default)."""
        policy_json = {
            "mode": "invalid_mode",
            "projects": []
        }
        policy = AccessPolicy.from_db_json(policy_json)
        
        assert policy.mode == "custom_projects"
        assert policy.projects == []
    
    def test_from_db_json_malformed_projects_defaults_to_empty_custom(self):
        """Test that malformed projects list defaults to empty custom."""
        policy_json = {
            "mode": "custom_projects",
            "projects": "not a list"
        }
        policy = AccessPolicy.from_db_json(policy_json)
        
        assert policy.mode == "custom_projects"
        assert policy.projects == []


class TestProjectAccessScope:
    """Tests for ProjectAccessScope model."""
    
    def test_grants_all_org_projects(self):
        """Test all_projects scope grants all org projects."""
        scope = ProjectAccessScope(
            mode="all_projects",
            project_ids=set()
        )
        
        assert scope.grants_all_org_projects is True
        assert scope.grants_no_projects is False
    
    def test_grants_no_projects_when_empty_custom(self):
        """Test empty custom scope grants no projects."""
        scope = ProjectAccessScope(
            mode="custom_projects",
            project_ids=set()
        )
        
        assert scope.grants_all_org_projects is False
        assert scope.grants_no_projects is True
    
    def test_custom_scope_with_projects(self):
        """Test custom scope with explicit project grants."""
        project_ids = {uuid.uuid4(), uuid.uuid4()}
        scope = ProjectAccessScope(
            mode="custom_projects",
            project_ids=project_ids
        )
        
        assert scope.grants_all_org_projects is False
        assert scope.grants_no_projects is False
        assert len(scope.project_ids) == 2


class TestAuthorizationContext:
    """Tests for AuthorizationContext model."""
    
    def test_is_active_true_for_active_user(self):
        """Test is_active property for active user."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="active",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )
        
        assert ctx.is_active is True
    
    def test_is_active_false_for_inactive_user(self):
        """Test is_active property for inactive user."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="suspended",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )
        
        assert ctx.is_active is False
    
    def test_context_is_immutable(self):
        """Test that AuthorizationContext is frozen/immutable."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="active",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )
        
        with pytest.raises((AttributeError, TypeError)):
            ctx.status = "suspended"  # type: ignore
