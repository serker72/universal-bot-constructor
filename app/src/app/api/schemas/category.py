"""Схемы категорий."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryIn(BaseModel):
    """Создание/обновление категории."""

    name: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class CategoryOut(BaseModel):
    """Категория."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
