"""Схемы полей заявки (справочник + привязки категорий + значения)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import RequestFieldType


# -- справочник полей ---------------------------------------------------------


class RequestFieldIn(BaseModel):
    """Создание поля справочника."""

    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    type: RequestFieldType
    label: str = Field(min_length=1, max_length=255)
    is_required_default: bool = False
    meta_data: dict | None = None


class RequestFieldUpdateIn(BaseModel):
    """Обновление поля справочника (PATCH: все поля опциональны)."""

    code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    type: RequestFieldType | None = None
    label: str | None = Field(default=None, min_length=1, max_length=255)
    is_required_default: bool | None = None
    meta_data: dict | None = None


class RequestFieldOut(BaseModel):
    """Поле справочника."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    type: RequestFieldType
    label: str
    is_required_default: bool
    meta_data: dict | None
    created_at: datetime
    updated_at: datetime


# -- привязка к категории -----------------------------------------------------


class CategoryFieldLinkIn(BaseModel):
    """Поле в составе формы категории (PUT /categories/{id}/fields)."""

    field_id: int
    sort_order: int = 0
    is_required: bool = False


class CategoryFieldsIn(BaseModel):
    """Замена состава полей категории (полный список)."""

    fields: list[CategoryFieldLinkIn] = Field(default_factory=list, max_length=50)


class CategoryFieldOut(BaseModel):
    """Поле, привязанное к категории."""

    field: RequestFieldOut
    sort_order: int
    is_required: bool


class CategoryFieldsOut(BaseModel):
    """Состав полей формы заявки категории."""

    category_id: int
    fields: list[CategoryFieldOut]


# -- значения полей заявки ----------------------------------------------------


class RequestFieldValueOut(BaseModel):
    """Значение поля заявки (в RequestOut.fields)."""

    field_id: int
    field_code: str
    field_label: str
    value: str | None
