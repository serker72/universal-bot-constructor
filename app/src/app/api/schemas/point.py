"""Схемы точек продаж (филиалов) и их привязок.

Валидация таймзоны и графика — в роутере (400, как прочие бизнес-ошибки;
pydantic дал бы 422).
"""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class PointIn(BaseModel):
    """Создание точки."""

    name: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="Europe/Moscow", min_length=1, max_length=64)
    work_interval_begin: time = time(9, 0)
    work_interval_end: time = time(19, 0)
    is_active: bool = True


class PointUpdateIn(BaseModel):
    """Обновление точки (PATCH: все поля опциональны)."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    work_interval_begin: time | None = None
    work_interval_end: time | None = None
    is_active: bool | None = None


class PointOut(BaseModel):
    """Точка продаж."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    timezone: str
    work_interval_begin: time
    work_interval_end: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PointCategoriesIn(BaseModel):
    """Замена списка id категорий точки."""

    category_ids: list[int]


class PointCategoriesOut(BaseModel):
    """Список id категорий точки."""

    point_id: int
    category_ids: list[int]


class PointObjectsIn(BaseModel):
    """Замена списка id объектов точки."""

    object_ids: list[int]


class PointObjectsOut(BaseModel):
    """Список id объектов точки."""

    point_id: int
    object_ids: list[int]
