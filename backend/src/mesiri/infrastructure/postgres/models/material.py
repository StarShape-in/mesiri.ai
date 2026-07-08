import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class MaterialCatalogModel(Base):
    """materials_catalog — the Material master list, org-scoped.

    Free-text `material_name` on receipts/usage links here via `material_id`
    once a catalog entry exists. Catalog is the join key for grouped reports;
    it carries no stock / balance state (see migration docstring for why).
    """

    __tablename__ = "materials_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    name = Column(String, nullable=False)
    default_unit = Column(String, nullable=True)
    category = Column(String, nullable=True)
    sku = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
