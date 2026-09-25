"""Связь многие-ко-многим: объекты <-> менеджеры."""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class ObjectManager(Base):
    """Назначение менеджера на объект."""

    __tablename__ = "object_managers"
    __table_args__ = (
        Index("uq_object_managers_object_id_user_id", "object_id", "user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )