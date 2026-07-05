from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SITE_MANAGER = "SITE_MANAGER"
    QUANTITY_SURVEYOR = "QUANTITY_SURVEYOR"
    WORKER = "WORKER"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLAlchemyEnum(UserRole, native_enum=False), nullable=False)
    whatsapp_number: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
