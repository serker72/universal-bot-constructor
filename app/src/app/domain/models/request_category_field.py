"""Привязка полей заявки к категории (состав и порядок полей диалога)."""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin


class RequestCategoryField(Base, TimestampMixin):
    """Поле справочника, включённое в форму заявки категории."""

    __tablename__ = "request_category_fields"
    __table_args__ = (
        Index(
            "uq_request_category_fields_category_id_field_id",
            "category_id",
            "field_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("request_available_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    field: Mapped["RequestAvailableField"] = relationship(
        back_populates="category_links",
    )
