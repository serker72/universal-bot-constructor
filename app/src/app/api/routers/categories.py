"""Роутер категорий (admin)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.category import CategoryIn, CategoryOut
from app.api.schemas.common import Page
from app.domain.models import Category
from app.repository.category import CategoryRepository

router = APIRouter(prefix="/categories", route_class=DishkaRoute, tags=["categories"])


@router.get("", response_model=Page[CategoryOut])
async def list_categories(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
    limit: int = 50,
    offset: int = 0,
) -> Page[CategoryOut]:
    """Список категорий (сортировка по sort_order, id)."""
    items = await repo.find(
        limit=limit,
        offset=offset,
        order_by=asc(Category.sort_order),
    )
    total = await repo.count()
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
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> CategoryOut:
    """Получить категорию."""
    category = await repo.get(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return CategoryOut.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    data: CategoryIn,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> CategoryOut:
    """Обновить категорию (name, sort_order, is_active)."""
    category = await repo.get(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    category.name = data.name
    category.sort_order = data.sort_order
    category.is_active = data.is_active
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[CategoryRepository],
) -> None:
    """Удалить категорию (вместе с объектами — CASCADE)."""
    category = await repo.get(category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    await repo.delete(category)
