import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class DeploymentType(str, enum.Enum):
    SAAS = "SaaS"
    ON_PREM = "On-Prem"

class OrganizationStatus(str, enum.Enum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"

class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True, nullable=False)
    deployment_type = Column(Enum(DeploymentType), nullable=False)
    db_route = Column(String, nullable=False)
    status = Column(Enum(OrganizationStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
