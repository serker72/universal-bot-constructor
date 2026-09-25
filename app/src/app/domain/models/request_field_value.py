"""Значения динамических полей заявки."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin

# Длина колонки value_text: ограничения полей (TEXT max_length, опции SELECT)
# валидируются против неё в API (_validate_meta_data)
VALUE_TEXT_MAX_LENGTH = 1024


class RequestField(Base, TimestampMixin):
    """Значение одного поля конкретной заявки (value_text — универсальное хранение)."""

    __tablename__ = "request_fields"
    __table_args__ = (
        Index(
            "uq_request_fields_request_id_field_id",
            "request_id",
            "field_id",
            unique=True,
        ),
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
    value_text: Mapped[str | None] = mapped_column(
        String(VALUE_TEXT_MAX_LENGTH), nullable=True
    )

    field: Mapped["RequestAvailableField"] = relationship()
    request: Mapped["Request"] = relationship(back_populates="values")
