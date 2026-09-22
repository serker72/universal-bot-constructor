"""Значения динамических полей заявки."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class RequestField(Base, TimestampMixin):
    """Значение одного поля конкретной заявки (value_text — универсальное хранение)."""

    __tablename__ = "request_fields"
    __table_args__ = (
        UniqueConstraint("request_id", "field_id", name="uq_request_fields_request_id_field_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("request_available_fields.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value_text: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    field: Mapped["RequestAvailableField"] = relationship()
    request: Mapped["Request"] = relationship(back_populates="values")
