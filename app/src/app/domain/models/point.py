"""Точки продаж (филиалы)."""

from datetime import time

from sqlalchemy import String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class Point(Base, TimestampMixin):
    """Точка продаж / филиал."""

    __tablename__ = "points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Название точки"
    )
    address: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Адрес точки"
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Moscow",
        server_default="Europe/Moscow",
        comment="Таймзона IANA",
    )
    work_interval_begin: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(9, 0), server_default="09:00:00"
    )
    work_interval_end: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(19, 0), server_default="19:00:00"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False
    )

    categories: Mapped[list["Category"]] = relationship(
        secondary="point_categories",
        viewonly=True,
    )
    objects: Mapped[list["Object"]] = relationship(
        secondary="point_objects",
        viewonly=True,
    )
