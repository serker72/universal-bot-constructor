"""Заявки посетителей на объекты."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class RequestStatus(str, enum.Enum):
    """Статусы заявки."""

    NEW = "new"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED_BY_CUSTOMER = "cancelled_by_customer"


class Request(Base, TimestampMixin):
    """Заявка посетителя на объект.

    Фиксированные поля: посетитель, объект, телефон, статус.
    Остальные данные — динамические поля (request_fields), состав
    которых настраивается по категории (request_category_fields).
    """

    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_status_created_at", "status", text("created_at DESC")),
        # список заявок без фильтра по статусу: ORDER BY created_at DESC, id DESC
        Index("ix_requests_created_at_id", text("created_at DESC"), text("id DESC")),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(
        ForeignKey("visitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="tp_request_status"),
        nullable=False,
        default=RequestStatus.NEW,
        server_default=text("'NEW'"),
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    visitor: Mapped["Visitor"] = relationship()
    object: Mapped["Object"] = relationship()
    # lazy="raise": значения загружаются только явно (selectinload в
    # RequestRepository), без скрытых запросов при каждой загрузке заявки
    values: Mapped[list["RequestField"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="raise",
    )