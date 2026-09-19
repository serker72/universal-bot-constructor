"""Схемы категорий."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryIn(BaseModel):
    """Создание категории."""

    name: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdateIn(BaseModel):
    """Обновление категории (PATCH: все поля опциональны)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    """Категория."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CategoryManagersIn(BaseModel):
    """Замена списка менеджеров категории."""

    user_ids: list[int]


class CategoryManagersOut(BaseModel):
    """Список id менеджеров категории."""

    category_id: int
    user_ids: list[int]
