"""Связь многие-ко-многим: точки продаж <-> категории."""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class PointCategory(Base):
    """Привязка категории к точке продаж (пусто = категория глобальная)."""

    __tablename__ = "point_categories"
    __table_args__ = (
        Index("uq_point_categories_point_id_category_id", "point_id", "category_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    point_id: Mapped[int] = mapped_column(
        ForeignKey("points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
