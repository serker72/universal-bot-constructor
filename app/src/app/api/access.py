"""Доступ пользователя к объектам и категориям (общая логика API).

Admin видит всё — функции возвращают ``None`` (без фильтрации).
Менеджер видит только свои объекты (прямые связи ``object_managers`` ∪
объекты назначенных категорий ``category_managers``) и связанные с ними
категории. Логика видимости объектов — в ``ObjectRepository``, категорий —
в ``CategoryRepository``; здесь только надстройка «admin/manager».
"""

from app.domain.models import User, UserRole
from app.repository.category import CategoryRepository
from app.repository.object import ObjectRepository


async def visible_object_ids(
    user: User, objects: ObjectRepository
) -> list[int] | None:
    """None — все объекты (admin), список — объекты менеджера."""
    if user.role == UserRole.ADMIN:
        return None
    return await objects.list_manager_object_ids(user.id)


async def visible_category_ids(
    user: User, categories: CategoryRepository
) -> list[int] | None:
    """None — все категории (admin), список — категории менеджера."""
    if user.role == UserRole.ADMIN:
        return None
    return await categories.list_manager_category_ids(user.id)
