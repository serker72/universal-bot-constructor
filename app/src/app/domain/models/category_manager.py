"""Связь многие-ко-многим: категории <-> менеджеры."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class CategoryManager(Base):
    """Назначение менеджера на категорию (доступ ко всем объектам категории)."""

    __tablename__ = "category_managers"
    __table_args__ = (
        UniqueConstraint("category_id", "user_id", name="uq_category_manager"),
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
