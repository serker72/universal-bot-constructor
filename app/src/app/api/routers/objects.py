"""Роутер объектов (admin: CRUD; менеджеры объекта — admin)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.common import Page
from app.api.schemas.object import ObjectIn, ObjectManagersIn, ObjectManagersOut, ObjectOut
from app.domain.models import Object
from app.repository.object import ObjectRepository
from app.repository.user import UserRepository

router = APIRouter(prefix="/objects", route_class=DishkaRoute, tags=["objects"])


def _to_out(obj: Object) -> ObjectOut:
    """ORM-объект в схему (has_pdf вычисляется)."""
    out = ObjectOut.model_validate(obj)
    out.has_pdf = bool(obj.pdf_path)
    return out


@router.get("", response_model=Page[ObjectOut])
async def list_objects(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
    category_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Page[ObjectOut]:
    """Список объектов (фильтр по категории, сортировка по sort_order)."""
    conditions = []
    if category_id is not None:
        conditions.append(Object.category_id == category_id)
    items = await repo.find(
        *conditions,
        limit=limit,
        offset=offset,
        order_by=asc(Object.sort_order),
    )
    total = await repo.count(*conditions)
    return Page(
        items=[_to_out(o) for o in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ObjectOut, status_code=status.HTTP_201_CREATED)
async def create_object(
    data: ObjectIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectOut:
    """Создать объект."""
    obj = Object(
        category_id=data.category_id,
        name=data.name,
        short_description=data.short_description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    try:
        await repo.add(obj)
    except IntegrityError:
        # несуществующая category_id (FK на уровне БД)
        await repo.session.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid category_id"
        ) from None
    return _to_out(obj)


@router.get("/{object_id}", response_model=ObjectOut)
async def get_object(
    object_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectOut:
    """Получить объект."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    return _to_out(obj)


@router.patch("/{object_id}", response_model=ObjectOut)
async def update_object(
    object_id: int,
    data: ObjectIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectOut:
    """Обновить объект."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    obj.category_id = data.category_id
    obj.name = data.name
    obj.short_description = data.short_description
    obj.sort_order = data.sort_order
    obj.is_active = data.is_active
    return _to_out(obj)


@router.delete("/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(
    object_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> None:
    """Удалить объект."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    await repo.delete(obj)


@router.get("/{object_id}/managers", response_model=ObjectManagersOut)
async def get_managers(
    object_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectManagersOut:
    """Список id менеджеров объекта."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    user_ids = await repo.list_manager_ids(object_id)
    return ObjectManagersOut(object_id=object_id, user_ids=user_ids)


@router.put("/{object_id}/managers", response_model=ObjectManagersOut)
async def set_managers(
    object_id: int,
    data: ObjectManagersIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
    users: FromDishka[UserRepository],
) -> ObjectManagersOut:
    """Заменить список менеджеров объекта."""
    obj = await repo.get(object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    # все указанные пользователи должны существовать и иметь роль manager
    for user_id in data.user_ids:
        user = await users.get(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"User {user_id} not found"
            )
    current = set(await repo.list_manager_ids(object_id))
    target = set(data.user_ids)
    for user_id in current - target:
        await repo.remove_manager(object_id, user_id)
    for user_id in target - current:
        await repo.add_manager(object_id, user_id)
    return ObjectManagersOut(object_id=object_id, user_ids=sorted(target))
