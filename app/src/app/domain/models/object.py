"""Объекты меню бота (элементы категорий)."""

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class Object(Base, TimestampMixin):
    """Объект внутри категории."""

    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(nullable=False)
    short_description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )
    pdf_path: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=text("''")
    )
    # file_id PDF в Telegram (повторная отправка без загрузки файла);
    # сбрасывается при замене PDF
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        default=0, server_default=text("0"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=text("true"), nullable=False
    )

    category: Mapped["Category"] = relationship(back_populates="objects")
    managers: Mapped[list["User"]] = relationship(
        secondary="object_managers",
        back_populates="managed_objects",
    )