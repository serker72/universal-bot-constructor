"""Схемы объектов и назначения менеджеров."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ObjectIn(BaseModel):
    """Создание/обновление объекта."""

    category_id: int
    name: str = Field(min_length=1, max_length=255)
    short_description: str = ""
    sort_order: int = 0
    is_active: bool = True


class ObjectOut(BaseModel):
    """Объект (pdf_path не раскрывается — доступ через /pdf)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    short_description: str
    sort_order: int
    is_active: bool
    has_pdf: bool = False  # вычисляется из pdf_path
    created_at: datetime
    updated_at: datetime


class ObjectManagersIn(BaseModel):
    """Замена списка менеджеров объекта."""

    user_ids: list[int]


class ObjectManagersOut(BaseModel):
    """Список id менеджеров объекта."""

    object_id: int
    user_ids: list[int]
