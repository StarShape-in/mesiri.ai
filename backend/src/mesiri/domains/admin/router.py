import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.infrastructure.postgres.dependency import get_db_conn
from mesiri.infrastructure.postgres.models.organization import (
    DeploymentType,
    OrganizationModel,
    OrganizationStatus,
)

router = APIRouter(prefix="/admin/organizations", tags=["admin"])


class OrganizationCreate(BaseModel):
    name: str
    deployment_type: DeploymentType
    db_route: str
    status: OrganizationStatus = OrganizationStatus.ACTIVE


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    deployment_type: DeploymentType
    db_route: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    org_in: OrganizationCreate, conn: AsyncConnection = Depends(get_db_conn)
):
    stmt = (
        insert(OrganizationModel)
        .values(
            name=org_in.name,
            deployment_type=org_in.deployment_type,
            db_route=org_in.db_route,
            status=org_in.status,
        )
        .returning(OrganizationModel)
    )

    result = await conn.execute(stmt)
    org_row = result.first()

    if not org_row:
        raise HTTPException(status_code=500, detail="Failed to create organization")

    org = org_row[0]
    return org


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(conn: AsyncConnection = Depends(get_db_conn)):
    result = await conn.execute(select(OrganizationModel))
    orgs = result.scalars().all()
    return orgs


class OrganizationProvision(BaseModel):
    name: str
    deployment_type: DeploymentType
    db_route: str
    admin_name: str
    admin_email: str
    admin_password: str


@router.post("/provision", response_model=OrganizationResponse)
async def provision_tenant(
    prov_in: OrganizationProvision, conn: AsyncConnection = Depends(get_db_conn)
):
    # 1. Create Organization
    stmt_org = (
        insert(OrganizationModel)
        .values(
            name=prov_in.name,
            deployment_type=prov_in.deployment_type,
            db_route=prov_in.db_route,
            status=OrganizationStatus.ACTIVE,
        )
        .returning(OrganizationModel)
    )

    result = await conn.execute(stmt_org)
    org_row = result.first()
    if not org_row:
        raise HTTPException(status_code=500, detail="Failed to create organization")
    org = org_row[0]

    # 2. Create Admin User
    from sqlalchemy.exc import IntegrityError

    from mesiri.domains.identity.auth_service import hash_password
    from mesiri.infrastructure.postgres.models.user import UserModel, UserRole

    hashed_pwd = hash_password(prov_in.admin_password)
    stmt_user = insert(UserModel).values(
        organization_id=org.id,
        email=prov_in.admin_email,
        hashed_password=hashed_pwd,
        full_name=prov_in.admin_name,
        role=UserRole.ADMIN,
    )

    try:
        await conn.execute(stmt_user)
    except IntegrityError as exc:
        # Email already exists
        raise HTTPException(status_code=400, detail="Admin email is already registered") from exc

    # 3. Commit transaction (if not auto-commit, but AsyncConnection execution is auto-committed in this context or managed by dependency, assuming managed)
    # Return the created organization
    return org
