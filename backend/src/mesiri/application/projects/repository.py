"""Project repository port (interface).

Defines the contract for project data access without coupling to
a specific implementation (PostgreSQL, fake, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

from mesiri_contracts.application.results.execution_result import ExecutionResult

from .create_commands import CreateProjectCommand
from .dtos import ProjectDTO

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


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


class CreateProjectExecutionRepository(ABC):
    """Persists CreateProjectCommand execution outcomes -- the confirmed-
    message (WhatsApp) write path, distinct from ProjectRepository above
    (read-only, REST). Mirrors application/finance/repository.py's
    AccountAdminExecutionRepository shape."""

    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_success(
        self, conn: AsyncConnection, cmd: CreateProjectCommand
    ) -> ExecutionResult:
        """Claim the idempotency key and insert the new project -- against
        `conn`. Assumes cmd is already valid (the Handler is responsible
        for that before calling this)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self, conn: AsyncConnection, idempotency_key: str, reasons: list[str]
    ) -> ExecutionResult:
        """Claim the idempotency key and record a REJECTED result -- no
        project row is written."""
        ...
