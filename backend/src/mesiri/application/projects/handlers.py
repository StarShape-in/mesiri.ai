"""Application handlers for project queries and commands.

Handlers orchestrate use cases by coordinating repositories, domain logic,
and authorization. They do not contain HTTP concerns or SQL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mesiri.authorization.context import AuthorizationContext
from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri_contracts.application.results.execution_result import ExecutionResult, as_replay
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .add_member_mapper import build_command as build_add_member_command
from .add_member_validation import validate as validate_add_member
from .create_mapper import build_command
from .create_site_mapper import build_command as build_site_command
from .create_site_validation import validate as validate_site
from .create_validation import validate
from .dtos import ProjectDTO
from .name_resolution import MemberNameResolver
from .queries import ListProjects
from .repository import (
    AddProjectMemberExecutionRepository,
    CreateProjectExecutionRepository,
    CreateSiteExecutionRepository,
    ProjectRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from .add_member_commands import AddProjectMemberCommand
    from .create_commands import CreateProjectCommand
    from .create_site_commands import CreateSiteCommand


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


class CreateProjectHandler:
    """Confirmed-message (WhatsApp) Project creation. Mirrors
    application/finance/handlers.py's ManageMoneyAccountHandler shape --
    handle() takes an externally-supplied connection (REST/tests can drive
    it directly); handle_confirmed() is the CQRS entry point that owns the
    one transaction."""

    def __init__(
        self,
        repo: CreateProjectExecutionRepository,
        db: PostgresDatabase | None = None,
    ) -> None:
        self._repo = repo
        self._db = db

    async def handle(self, conn: AsyncConnection, cmd: CreateProjectCommand) -> ExecutionResult:
        reasons = validate(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)


class CreateSiteHandler:
    """Confirmed-message (WhatsApp) Site creation. Mirrors CreateProjectHandler
    above exactly."""

    def __init__(
        self,
        repo: CreateSiteExecutionRepository,
        db: PostgresDatabase | None = None,
    ) -> None:
        self._repo = repo
        self._db = db

    async def handle(self, conn: AsyncConnection, cmd: CreateSiteCommand) -> ExecutionResult:
        reasons = validate_site(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_site_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)


class AddProjectMemberHandler:
    """Confirmed-message (WhatsApp) project-member addition. Mirrors
    application/automations/handlers.py's CreateAutomationHandler shape --
    handle() resolves member_name into member_user_id (a DB round trip, so
    it cannot happen in the pure workflow node -- see workflows/
    add_project_member/nodes.py's docstring) before running the ordinary
    structural validate(). A name that doesn't resolve to any active org
    user is a rejection, same "hard rejection, never a silent default"
    reasoning application/finance/resolution.py's docstring states for
    account names -- there is no sensible partial success for "add this
    person" the way there can be for a multi-name audience."""

    def __init__(
        self,
        repo: AddProjectMemberExecutionRepository,
        name_resolver: MemberNameResolver,
        db: PostgresDatabase | None = None,
    ) -> None:
        self._repo = repo
        self._name_resolver = name_resolver
        self._db = db

    async def handle(
        self, conn: AsyncConnection, cmd: AddProjectMemberCommand
    ) -> ExecutionResult:
        if not cmd.member_user_id and cmd.member_name:
            resolved = await self._name_resolver.resolve(
                conn, organization_id=cmd.organization_id, name=cmd.member_name
            )
            if resolved is None:
                reasons = [f"couldn't find an active user named {cmd.member_name}"]
                existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
                if existing is not None:
                    return as_replay(existing)
                return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
            cmd = cmd.model_copy(update={"member_user_id": resolved})

        reasons = validate_add_member(cmd)

        existing = await self._repo.check_idempotency(conn, cmd.idempotency_key)
        if existing is not None:
            return as_replay(existing)

        if reasons:
            return await self._repo.persist_rejection(conn, cmd.idempotency_key, reasons)
        return await self._repo.persist_success(conn, cmd)

    async def handle_confirmed(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        """CQRS entry point (WhatsApp M8 path) — owns the one transaction."""
        assert self._db is not None, "handle_confirmed requires db to be wired"
        cmd = build_add_member_command(confirmed)
        async with self._db.transaction() as conn:
            return await self.handle(conn, cmd)
