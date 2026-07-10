"""Project repository port (interface).

Defines the contract for project data access without coupling to
a specific implementation (PostgreSQL, fake, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .dtos import ProjectDTO


class ProjectRepository(ABC):
    """Abstract repository for project data access.

    Implementations must enforce the access scope provided by the caller.
    The repository should NOT make authorization decisions; it receives
    an already-resolved access scope and queries accordingly.
    """

    @abstractmethod
    async def list_projects_by_scope(
        self,
        organization_id: UUID,
        *,
        all_projects: bool,
        project_ids: set[UUID] | None = None,
    ) -> list[ProjectDTO]:
        """List projects according to the provided access scope.

        Args:
            organization_id: Organization to query (always enforced)
            all_projects: If True, return all org projects
            project_ids: If all_projects=False, return only these project IDs

        Returns:
            List of projects ordered by name (ascending)

        Important:
            If all_projects=False and project_ids is empty set, returns empty list.
            This ensures empty custom access scopes return zero projects.
        """
        ...
