"""Пользователи (admin / manager)."""

import enum

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """Роли пользователей системы."""

    ADMIN = "admin"
    MANAGER = "manager"


class User(Base, TimestampMixin):
    """Учётная запись администратора или менеджера."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="tp_user_role"),
        nullable=False,
        default=UserRole.MANAGER,
    )
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    managed_objects: Mapped[list["Object"]] = relationship(
        secondary="object_managers",
        back_populates="managers",
    )