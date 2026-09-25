"""Пользователи (admin / manager)."""

import enum

from sqlalchemy import BigInteger, Enum, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """Роли пользователей системы."""

    ADMIN = "admin"
    MANAGER = "manager"


class User(Base, TimestampMixin):
    """Учётная запись администратора или менеджера."""

    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_username", "username", unique=True),
        Index("uq_users_telegram_id", "telegram_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="tp_user_role"),
        nullable=False,
        default=UserRole.MANAGER,
        server_default=text("'MANAGER'"),
    )
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=text("true"), nullable=False
    )

    managed_objects: Mapped[list["Object"]] = relationship(
        secondary="object_managers",
        back_populates="managers",
    )
    managed_categories: Mapped[list["Category"]] = relationship(
        secondary="category_managers",
        back_populates="managers",
    )