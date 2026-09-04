"""Категории меню бота."""

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    """Категория меню бота."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    objects: Mapped[list["Object"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )