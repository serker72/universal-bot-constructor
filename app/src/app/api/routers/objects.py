"""Роутер объектов.

- admin — CRUD, назначение менеджеров;
- manager — чтение своих объектов (прямые связи ∪ объекты категорий).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.access import visible_object_ids
from app.api.deps import AdminUser, flush_or_400, get_or_404
from app.api.managers_sync import sync_managers
from app.api.schemas.common import LimitQuery, OffsetQuery, Page
from app.api.schemas.object import (
    ObjectIn,
    ObjectManagersIn,
    ObjectManagersOut,
    ObjectOut,
    ObjectUpdateIn,
)
from app.domain.models import Object, User
from app.repository.object import ObjectRepository
from app.repository.user import UserRepository
from app.services.pdf import PdfService

router = APIRouter(prefix="/objects", route_class=TransactionalRoute, tags=["objects"])


def _to_out(obj: Object) -> ObjectOut:
    """ORM-объект в схему (has_pdf вычисляется)."""
    out = ObjectOut.model_validate(obj)
    out.has_pdf = bool(obj.pdf_path)
    return out


@router.get("", response_model=Page[ObjectOut])
async def list_objects(
    user: FromDishka[User],
    repo: FromDishka[ObjectRepository],
    category_id: int | None = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[ObjectOut]:
    """Список объектов (admin — все; менеджер — свои; фильтр по категории)."""
    conditions = []
    if category_id is not None:
        conditions.append(Object.category_id == category_id)
    object_ids = await visible_object_ids(user, repo)
    if object_ids is not None:
        # пустой список → пустая выборка (SQLAlchemy рендерит пустое IN как ложь)
        conditions.append(Object.id.in_(object_ids))
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
    repo.session.add(obj)
    # несуществующая category_id (FK на уровне БД) — 400 до ответа
    await flush_or_400(repo.session, "Invalid category_id")
    return _to_out(obj)


@router.get("/{object_id}", response_model=ObjectOut)
async def get_object(
    object_id: int,
    user: FromDishka[User],
    repo: FromDishka[ObjectRepository],
) -> ObjectOut:
    """Получить объект (менеджер — только свой)."""
    obj = get_or_404(await repo.get(object_id), "Object not found")
    object_ids = await visible_object_ids(user, repo)
    if object_ids is not None and obj.id not in object_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found")
    return _to_out(obj)


@router.patch("/{object_id}", response_model=ObjectOut)
async def update_object(
    object_id: int,
    data: ObjectUpdateIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectOut:
    """Обновить объект (PATCH: только переданные поля)."""
    obj = get_or_404(await repo.get(object_id), "Object not found")
    # PATCH-семантика: None (не передано) — поле не меняется
    if data.category_id is not None:
        obj.category_id = data.category_id
    if data.name is not None:
        obj.name = data.name
    if data.short_description is not None:
        obj.short_description = data.short_description
    if data.sort_order is not None:
        obj.sort_order = data.sort_order
    if data.is_active is not None:
        obj.is_active = data.is_active
    # FK category_id проверяется БД до ответа (а не на commit после него)
    await flush_or_400(repo.session, "Invalid category_id")
    # updated_at (server onupdate) истёк после flush — перечитать до сериализации
    await repo.session.refresh(obj)
    return _to_out(obj)


@router.delete("/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(
    object_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> None:
    """Удалить объект (вместе с PDF-файлом с диска).

    Файл удаляется после commit: при откате транзакции запись и файл остаются.
    """
    obj = get_or_404(await repo.get(object_id), "Object not found")
    pdf_path = obj.pdf_path
    await repo.delete(obj)
    await repo.session.commit()
    if pdf_path:
        pdf.delete(pdf_path)


@router.get("/{object_id}/managers", response_model=ObjectManagersOut)
async def get_managers(
    object_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[ObjectRepository],
) -> ObjectManagersOut:
    """Список id менеджеров объекта."""
    get_or_404(await repo.get(object_id), "Object not found")
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
    """Заменить список менеджеров объекта (только роль manager)."""
    get_or_404(await repo.get(object_id), "Object not found")
    user_ids = await sync_managers(
        repo, object_id, data.user_ids, users, require_manager_role=True
    )
    return ObjectManagersOut(object_id=object_id, user_ids=user_ids)
