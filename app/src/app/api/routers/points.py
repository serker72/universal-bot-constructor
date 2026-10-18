"""Роутер точек продаж (филиалов) — только admin.

CRUD точек + привязки категорий/объектов (GET/PUT, diff-замена по
образцу sync_managers). Без этого контура точки нельзя завести,
а бот фильтрует меню именно по ним.

Валидация таймзоны и графика — здесь (400), а не в pydantic (422):
ошибки бизнес-правил однотипны с остальными 400 роутеров.
"""

from datetime import time
from zoneinfo import available_timezones

from dishka.integrations.fastapi import FromDishka
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc

from app.api.deps import AdminUser, get_or_404
from app.api.routing import TransactionalRoute
from app.api.schemas.common import LimitQuery, OffsetQuery, Page
from app.api.schemas.point import (
    PointCategoriesIn,
    PointCategoriesOut,
    PointIn,
    PointObjectsIn,
    PointObjectsOut,
    PointOut,
    PointUpdateIn,
)
from app.domain.models import Category, Object, Point
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.point import PointRepository

router = APIRouter(prefix="/points", route_class=TransactionalRoute, tags=["points"])


def _validate_timezone(value: str) -> None:
    """IANA-имя таймзоны (400 при неизвестной)."""
    if value not in available_timezones():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Неизвестная таймзона: {value}"
        )


def _validate_interval(begin: time, end: time) -> None:
    """График работы: начало строго раньше окончания."""
    if begin >= end:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Начало графика должно быть раньше окончания",
        )


@router.get("", response_model=Page[PointOut])
async def list_points(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[PointOut]:
    """Список точек (по наименованию)."""
    items = await repo.find(limit=limit, offset=offset, order_by=asc(Point.name))
    total = await repo.count()
    return Page(
        items=[PointOut.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PointOut, status_code=status.HTTP_201_CREATED)
async def create_point(
    data: PointIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> PointOut:
    """Создать точку."""
    _validate_timezone(data.timezone)
    _validate_interval(data.work_interval_begin, data.work_interval_end)
    point = Point(
        name=data.name,
        address=data.address,
        timezone=data.timezone,
        work_interval_begin=data.work_interval_begin,
        work_interval_end=data.work_interval_end,
        is_active=data.is_active,
    )
    await repo.add(point)
    return PointOut.model_validate(point)


@router.get("/{point_id}", response_model=PointOut)
async def get_point(
    point_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> PointOut:
    """Получить точку."""
    return PointOut.model_validate(
        get_or_404(await repo.get(point_id), "Point not found")
    )


@router.patch("/{point_id}", response_model=PointOut)
async def update_point(
    point_id: int,
    data: PointUpdateIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> PointOut:
    """Обновить точку (PATCH: только переданные поля)."""
    point = get_or_404(await repo.get(point_id), "Point not found")
    if data.timezone is not None:
        _validate_timezone(data.timezone)
        point.timezone = data.timezone
    # график проверяется по объединённым значениям (можно менять половину)
    if data.work_interval_begin is not None or data.work_interval_end is not None:
        begin = (
            data.work_interval_begin
            if data.work_interval_begin is not None
            else point.work_interval_begin
        )
        end = (
            data.work_interval_end
            if data.work_interval_end is not None
            else point.work_interval_end
        )
        _validate_interval(begin, end)
        point.work_interval_begin = begin
        point.work_interval_end = end
    if data.name is not None:
        point.name = data.name
    if data.address is not None:
        point.address = data.address
    if data.is_active is not None:
        point.is_active = data.is_active
    await repo.session.flush()
    await repo.session.refresh(point)
    return PointOut.model_validate(point)


@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_point(
    point_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> None:
    """Удалить точку (связи с категориями/объектами — CASCADE; у посетителей
    point_id обнулится SET NULL)."""
    point = get_or_404(await repo.get(point_id), "Point not found")
    await repo.delete(point)
    await repo.session.commit()


# -- привязки категорий --------------------------------------------------------


async def _check_categories_exist(
    categories: CategoryRepository, category_ids: set[int]
) -> None:
    if not category_ids:
        return
    found = await categories.find(Category.id.in_(category_ids))
    missing = category_ids - {c.id for c in found}
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Category(ies) not found: {', '.join(str(i) for i in sorted(missing))}",
        )


async def _check_objects_exist(
    objects: ObjectRepository, object_ids: set[int]
) -> None:
    if not object_ids:
        return
    found = await objects.find(Object.id.in_(object_ids))
    missing = object_ids - {o.id for o in found}
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Object(s) not found: {', '.join(str(i) for i in sorted(missing))}",
        )


@router.get("/{point_id}/categories", response_model=PointCategoriesOut)
async def get_categories(
    point_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> PointCategoriesOut:
    """Список id категорий точки (пусто — точка берёт все глобальные)."""
    get_or_404(await repo.get(point_id), "Point not found")
    return PointCategoriesOut(
        point_id=point_id, category_ids=await repo.list_category_ids(point_id)
    )


@router.put("/{point_id}/categories", response_model=PointCategoriesOut)
async def set_categories(
    point_id: int,
    data: PointCategoriesIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
    categories: FromDishka[CategoryRepository],
) -> PointCategoriesOut:
    """Заменить список категорий точки (diff; неизвестный id — 400)."""
    get_or_404(await repo.get(point_id), "Point not found")
    target = set(data.category_ids)
    await _check_categories_exist(categories, target)
    await repo.sync_categories(point_id, target)
    return PointCategoriesOut(point_id=point_id, category_ids=sorted(target))


# -- привязки объектов ----------------------------------------------------------


@router.get("/{point_id}/objects", response_model=PointObjectsOut)
async def get_objects(
    point_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
) -> PointObjectsOut:
    """Список id объектов точки (пусто — точка берёт все глобальные)."""
    get_or_404(await repo.get(point_id), "Point not found")
    return PointObjectsOut(
        point_id=point_id, object_ids=await repo.list_object_ids(point_id)
    )


@router.put("/{point_id}/objects", response_model=PointObjectsOut)
async def set_objects(
    point_id: int,
    data: PointObjectsIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[PointRepository],
    objects: FromDishka[ObjectRepository],
) -> PointObjectsOut:
    """Заменить список объектов точки (diff; неизвестный id — 400)."""
    get_or_404(await repo.get(point_id), "Point not found")
    target = set(data.object_ids)
    await _check_objects_exist(objects, target)
    await repo.sync_objects(point_id, target)
    return PointObjectsOut(point_id=point_id, object_ids=sorted(target))
