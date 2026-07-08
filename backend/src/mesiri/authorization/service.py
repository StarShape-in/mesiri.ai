"""Authorization service for resolving request authorization context.

Responsible for loading the current user from the database, verifying their
status and organization membership, and resolving their access scope.
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from .context import AccessPolicy, AuthorizationContext, ProjectAccessScope


class AuthorizationService:
    """Service for resolving authorization context from JWT claims."""
    
    def __init__(self, conn: AsyncConnection):
        """Initialize with database connection."""
        self._conn = conn
        
        # Define users table structure inline (repository pattern applied later)
        self._users = sa.Table(
            "users",
            sa.MetaData(),
            sa.Column("id", sa.UUID(as_uuid=True)),
            sa.Column("organization_id", sa.UUID(as_uuid=True)),
            sa.Column("role", sa.String),
            sa.Column("status", sa.String),
            sa.Column("access_policy", sa.JSON),
        )
    
    async def resolve_from_jwt(
        self,
        user_id: UUID,
        org_id: UUID,
        role: str,
    ) -> AuthorizationContext:
        """Resolve authorization context from JWT claims.
        
        Loads current user from database and verifies:
        - User exists
        - User belongs to claimed organization
        - User status is active
        - Access policy is valid
        
        Returns:
            AuthorizationContext with resolved access scope
            
        Raises:
            HTTPException 401: User not found, disabled, or org mismatch
        """
        # Load current user from database
        result = await self._conn.execute(
            sa.select(
                self._users.c.id,
                self._users.c.organization_id,
                self._users.c.role,
                self._users.c.status,
                self._users.c.access_policy,
            ).where(self._users.c.id == user_id)
        )
        rows = result.fetchall()
        row = rows[0] if rows else None
        
        if row is None:
            raise HTTPException(
                status_code=401,
                detail="User not found or token invalid"
            )
        
        # Verify organization consistency
        if row.organization_id != org_id:
            raise HTTPException(
                status_code=401,
                detail="Organization mismatch"
            )
        
        # Verify user status
        user_status = row.status or "active"
        if user_status != "active":
            raise HTTPException(
                status_code=401,
                detail=f"User account is {user_status}"
            )
        
        # Parse and validate access policy
        access_policy = AccessPolicy.from_db_json(row.access_policy)
        
        # Resolve project access scope
        project_scope = self._resolve_project_scope(access_policy, org_id)
        
        return AuthorizationContext(
            user_id=row.id,
            organization_id=row.organization_id,
            role=row.role,
            status=user_status,
            access_policy=access_policy,
            project_scope=project_scope,
        )
    
    def _resolve_project_scope(
        self,
        access_policy: AccessPolicy,
        org_id: UUID,
    ) -> ProjectAccessScope:
        """Resolve project access scope from access policy.
        
        Rules:
        - all_projects mode: grants access to all projects in organization
        - custom_projects mode: grants access only to explicitly listed projects
        - Empty custom projects list: grants access to zero projects
        
        Returns:
            ProjectAccessScope with mode and explicit project IDs if custom
        """
        if access_policy.mode == "all_projects":
            # User has access to all org projects; no need to list them
            return ProjectAccessScope(
                mode="all_projects",
                project_ids=set()
            )
        
        # custom_projects mode: extract explicit project IDs
        project_ids: set[UUID] = set()
        for project_grant in access_policy.projects:
            if isinstance(project_grant, dict):
                project_id_str = project_grant.get("projectId")
                if project_id_str:
                    try:
                        project_ids.add(UUID(project_id_str))
                    except (ValueError, TypeError):
                        # Malformed project ID; skip it
                        pass
        
        return ProjectAccessScope(
            mode="custom_projects",
            project_ids=project_ids
        )
