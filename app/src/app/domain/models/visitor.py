"""Посетители (клиенты бота)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, TimestampMixin


class Visitor(Base, TimestampMixin):
    """Посетитель, зарегистрированный через бота."""

    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(nullable=False)
    consent_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_blocked: Mapped[bool] = mapped_column(default=False, nullable=False)
    blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )