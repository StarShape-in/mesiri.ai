"""Unit tests for ListProjectsHandler.

Tests the application handler logic without requiring database.
Uses a fake repository implementation.
"""

from __future__ import annotations

import uuid

import pytest

from mesiri.application.projects.dtos import ProjectDTO
from mesiri.application.projects.handlers import ListProjectsHandler
from mesiri.application.projects.queries import ListProjects
from mesiri.application.projects.repository import ProjectRepository
from mesiri.authorization.context import (
    AccessPolicy,
    AuthorizationContext,
    ProjectAccessScope,
)


class FakeProjectRepository(ProjectRepository):
    """Fake repository for testing without database."""
    
    def __init__(self):
        self.projects: list[ProjectDTO] = []
        self.last_query_org_id: uuid.UUID | None = None
        self.last_query_all_projects: bool | None = None
        self.last_query_project_ids: set[uuid.UUID] | None = None
    
    async def list_projects_by_scope(
        self,
        organization_id: uuid.UUID,
        *,
        all_projects: bool,
        project_ids: set[uuid.UUID] | None = None,
    ) -> list[ProjectDTO]:
        """Return pre-configured projects, recording query parameters."""
        self.last_query_org_id = organization_id
        self.last_query_all_projects = all_projects
        self.last_query_project_ids = project_ids
        
        if not all_projects and (project_ids is None or len(project_ids) == 0):
            return []
        
        if all_projects:
            return [p for p in self.projects if p.organization_id == organization_id]
        
        return [
            p for p in self.projects
            if p.organization_id == organization_id and p.id in project_ids
        ]


@pytest.fixture
def fake_repository():
    """Create fake repository."""
    return FakeProjectRepository()


@pytest.fixture
def sample_org_id():
    """Sample organization ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_projects(sample_org_id):
    """Create sample project DTOs."""
    return [
        ProjectDTO(
            id=uuid.uuid4(),
            organization_id=sample_org_id,
            name="Alpha Project",
            code="ALPHA",
            location="New York",
            client="Acme Corp",
            description="Test project",
            status="on_track",
            progress=50,
            open_issues=2,
        ),
        ProjectDTO(
            id=uuid.uuid4(),
            organization_id=sample_org_id,
            name="Beta Project",
            code="BETA",
            location="Boston",
            client="Beta Inc",
            description="Another test",
            status="at_risk",
            progress=75,
            open_issues=5,
        ),
    ]


async def test_handler_all_projects_scope(
    fake_repository,
    sample_org_id,
    sample_user_id,
    sample_projects,
):
    """Test handler with all_projects scope."""
    fake_repository.projects = sample_projects
    
    auth_context = AuthorizationContext(
        user_id=sample_user_id,
        organization_id=sample_org_id,
        role="admin",
        status="active",
        access_policy=AccessPolicy(mode="all_projects", projects=[]),
        project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
    )
    
    handler = ListProjectsHandler(fake_repository)
    query = ListProjects()
    
    result = await handler.handle(query, auth_context)
    
    assert len(result) == 2
    assert fake_repository.last_query_all_projects is True
    assert fake_repository.last_query_org_id == sample_org_id


async def test_handler_custom_projects_scope(
    fake_repository,
    sample_org_id,
    sample_user_id,
    sample_projects,
):
    """Test handler with custom_projects scope."""
    fake_repository.projects = sample_projects
    
    # Grant access to only first project
    granted_project_id = sample_projects[0].id
    
    auth_context = AuthorizationContext(
        user_id=sample_user_id,
        organization_id=sample_org_id,
        role="user",
        status="active",
        access_policy=AccessPolicy(
            mode="custom_projects",
            projects=[{"projectId": str(granted_project_id)}]
        ),
        project_scope=ProjectAccessScope(
            mode="custom_projects",
            project_ids={granted_project_id}
        ),
    )
    
    handler = ListProjectsHandler(fake_repository)
    query = ListProjects()
    
    result = await handler.handle(query, auth_context)
    
    assert len(result) == 1
    assert result[0].id == granted_project_id
    assert fake_repository.last_query_all_projects is False
    assert granted_project_id in fake_repository.last_query_project_ids


async def test_handler_empty_custom_scope_returns_empty(
    fake_repository,
    sample_org_id,
    sample_user_id,
    sample_projects,
):
    """Test handler with empty custom scope returns no projects."""
    fake_repository.projects = sample_projects
    
    auth_context = AuthorizationContext(
        user_id=sample_user_id,
        organization_id=sample_org_id,
        role="user",
        status="active",
        access_policy=AccessPolicy(mode="custom_projects", projects=[]),
        project_scope=ProjectAccessScope(mode="custom_projects", project_ids=set()),
    )
    
    handler = ListProjectsHandler(fake_repository)
    query = ListProjects()
    
    result = await handler.handle(query, auth_context)
    
    assert len(result) == 0
    assert fake_repository.last_query_all_projects is False


async def test_handler_respects_organization_isolation(
    fake_repository,
    sample_user_id,
):
    """Test handler passes correct organization ID to repository."""
    user_org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    
    # Add projects from two different orgs
    fake_repository.projects = [
        ProjectDTO(
            id=uuid.uuid4(),
            organization_id=user_org_id,
            name="User Org Project",
            code=None,
            location=None,
            client=None,
            description=None,
            status="on_track",
            progress=0,
            open_issues=0,
        ),
        ProjectDTO(
            id=uuid.uuid4(),
            organization_id=other_org_id,
            name="Other Org Project",
            code=None,
            location=None,
            client=None,
            description=None,
            status="on_track",
            progress=0,
            open_issues=0,
        ),
    ]
    
    auth_context = AuthorizationContext(
        user_id=sample_user_id,
        organization_id=user_org_id,
        role="admin",
        status="active",
        access_policy=AccessPolicy(mode="all_projects", projects=[]),
        project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
    )
    
    handler = ListProjectsHandler(fake_repository)
    query = ListProjects()
    
    result = await handler.handle(query, auth_context)
    
    # Should only get user's org projects
    assert len(result) == 1
    assert result[0].organization_id == user_org_id
    assert fake_repository.last_query_org_id == user_org_id
