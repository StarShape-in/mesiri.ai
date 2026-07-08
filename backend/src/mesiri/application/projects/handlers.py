"""Application handlers for project queries and commands.

Handlers orchestrate use cases by coordinating repositories, domain logic,
and authorization. They do not contain HTTP concerns or SQL.
"""

from __future__ import annotations

from mesiri.authorization.context import AuthorizationContext

from .dtos import ProjectDTO
from .queries import ListProjects
from .repository import ProjectRepository


class ListProjectsHandler:
    """Handler for listing projects accessible to current user.
    
    Orchestrates:
    1. Extract access scope from authorization context
    2. Query repository with resolved scope
    3. Return project DTOs
    """
    
    def __init__(self, repository: ProjectRepository):
        """Initialize with project repository."""
        self._repository = repository
    
    async def handle(
        self,
        query: ListProjects,
        auth_context: AuthorizationContext,
    ) -> list[ProjectDTO]:
        """Execute list projects query.
        
        Args:
            query: ListProjects query (marker, no parameters)
            auth_context: Current user's authorization context with resolved scope
            
        Returns:
            List of projects accessible to the user, ordered by name
        """
        # Extract access scope from authorization context
        scope = auth_context.project_scope
        
        # Query repository according to scope
        return await self._repository.list_projects_by_scope(
            organization_id=auth_context.organization_id,
            all_projects=scope.grants_all_org_projects,
            project_ids=scope.project_ids if not scope.grants_all_org_projects else None,
        )
