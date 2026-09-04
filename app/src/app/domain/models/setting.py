"""Настройки системы (ключ-значение)."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class Setting(Base):
    """Значение настройки по ключу."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)