"""Связь многие-ко-многим: категории <-> менеджеры."""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class CategoryManager(Base):
    """Назначение менеджера на категорию (доступ ко всем объектам категории)."""

    __tablename__ = "category_managers"
    __table_args__ = (
        Index("uq_category_managers_category_id_user_id", "category_id", "user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
