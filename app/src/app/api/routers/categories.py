"""Роутер категорий.

- admin — CRUD, назначение менеджеров;
- manager — чтение доступных категорий (назначенные напрямую ∪ категории
  своих объектов).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.access import visible_category_ids
from app.api.deps import AdminUser, get_or_404
from app.api.managers_sync import sync_managers
from app.api.schemas.category import (
    CategoryIn,
    CategoryManagersIn,
    CategoryManagersOut,
    CategoryOut,
    CategoryUpdateIn,
)
from app.api.schemas.common import Page
from app.domain.models import Category, User
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository
from app.repository.user import UserRepository
from app.services.pdf import PdfService

router = APIRouter(prefix="/categories", route_class=DishkaRoute, tags=["categories"])


@router.get("", response_model=Page[CategoryOut])
async def list_categories(
    user: FromDishka[User],
    repo: FromDishka[CategoryRepository],
    limit: int = 50,
    offset: int = 0,
) -> Page[CategoryOut]:
    """Список категорий (admin — все; менеджер — доступные)."""
    conditions = []
    category_ids = await visible_category_ids(user, repo)
    if category_ids is not None:
        # пустой список → пустая выборка (SQLAlchemy рендерит пустое IN как ложь)
        conditions.append(Category.id.in_(category_ids))
    items = await repo.find(
        *conditions,
        limit=limit,
        offset=offset,
        order_by=asc(Category.sort_order),
    )
    total = await repo.count(*conditions)
    return Page(
        items=[CategoryOut.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> CategoryOut:
    """Создать категорию."""
    category = Category(
        name=data.name, sort_order=data.sort_order, is_active=data.is_active
    )
    await repo.add(category)
    return CategoryOut.model_validate(category)


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: int,
    user: FromDishka[User],
    repo: FromDishka[CategoryRepository],
) -> CategoryOut:
    """Получить категорию (менеджер — только доступную)."""
    category = get_or_404(
        await repo.get(category_id), "Category not found"
    )
    category_ids = await visible_category_ids(user, repo)
    if category_ids is not None and category.id not in category_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return CategoryOut.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    data: CategoryUpdateIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> CategoryOut:
    """Обновить категорию (PATCH: только переданные поля)."""
    category = get_or_404(await repo.get(category_id), "Category not found")
    # PATCH-семантика: None (не передано) — поле не меняется
    if data.name is not None:
        category.name = data.name
    if data.sort_order is not None:
        category.sort_order = data.sort_order
    if data.is_active is not None:
        category.is_active = data.is_active
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
    objects: FromDishka[ObjectRepository],
    pdf: FromDishka[PdfService],
) -> None:
    """Удалить категорию (вместе с объектами и их PDF-файлами — CASCADE)."""
    category = get_or_404(await repo.get(category_id), "Category not found")
    # pdf_path объектов удаляется вместе с объектами (FK CASCADE) —
    # чистим файлы до удаления записей
    for obj in await objects.list_by_category(category_id):
        if obj.pdf_path:
            pdf.delete(obj.pdf_path)
    await repo.delete(category)


@router.get("/{category_id}/managers", response_model=CategoryManagersOut)
async def get_managers(
    category_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> CategoryManagersOut:
    """Список id менеджеров категории."""
    category = get_or_404(
        await repo.get(category_id), "Category not found"
    )
    user_ids = await repo.list_manager_ids(category_id)
    return CategoryManagersOut(category_id=category_id, user_ids=user_ids)


@router.put("/{category_id}/managers", response_model=CategoryManagersOut)
async def set_managers(
    category_id: int,
    data: CategoryManagersIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
    users: FromDishka[UserRepository],
) -> CategoryManagersOut:
    """Заменить список менеджеров категории (доступ ко всем объектам
    категории)."""
    category = get_or_404(
        await repo.get(category_id), "Category not found"
    )
    user_ids = await sync_managers(repo, category_id, data.user_ids, users)
    return CategoryManagersOut(category_id=category_id, user_ids=user_ids)
