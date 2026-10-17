"""Посетители (клиенты бота)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base, TimestampMixin


class Visitor(Base, TimestampMixin):
    """Посетитель, зарегистрированный через бота."""

    __tablename__ = "visitors"
    __table_args__ = (Index("uq_visitors_telegram_id", "telegram_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Выбранная точка продаж (источник истины; NULL — точка не выбрана;
    # удаляется точка — посетитель остаётся, выбор сбрасывается)
    point_id: Mapped[int | None] = mapped_column(
        ForeignKey("points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    consent_given: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_blocked: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )