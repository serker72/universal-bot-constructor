"""Справочник доступных полей заявки (динамический конструктор)."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class RequestFieldType(str, enum.Enum):
    """Типы полей динамической формы заявки."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"       # выбор часа и минут (два окна)
    SELECT = "select"


class RequestAvailableField(Base, TimestampMixin):
    """Поле заявки из справочника (настраивается админом).

    meta_data — параметры по типу:
    - SELECT: {"options": ["Вариант 1", ...]}
    - TIME:   {"minute_step": 15}
    - NUMBER: {"min": 1, "max": 100}
    - TEXT:   {"max_length": 500}
    """

    __tablename__ = "request_available_fields"
    __table_args__ = (
        Index("uq_request_available_fields_code", "code", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[RequestFieldType] = mapped_column(
        Enum(
            RequestFieldType,
            name="tp_request_field_type",
            # хранить значения enum ("text"), а не имена ("TEXT")
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # FK request_category_fields.field_id — ON DELETE CASCADE: привязки к
    # категориям удаляет БД (passive_deletes), ORM не делает UPDATE ... SET
    # field_id = NULL (NOT NULL → IntegrityError и ложный 400 при удалении)
    category_links: Mapped[list["RequestCategoryField"]] = relationship(
        back_populates="field",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )