"""Связь многие-ко-многим: точки продаж <-> объекты."""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class PointObject(Base):
    """Привязка объекта к точке продаж (пусто = объект глобальный)."""

    __tablename__ = "point_objects"
    __table_args__ = (
        Index("uq_point_objects_point_id_object_id", "point_id", "object_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    point_id: Mapped[int] = mapped_column(
        ForeignKey("points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
