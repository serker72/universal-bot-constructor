"""Репозиторий категорий."""

from collections.abc import Sequence

from sqlalchemy import asc, exists, select

from app.domain.models import Category, CategoryManager, Object, ObjectManager
from app.domain.models.point_category import PointCategory
from app.repository.base import BaseRepository
from app.repository.manager_link import ManagerLinkMixin, link_entity
from app.repository.point_scope import point_visible_condition


class CategoryRepository(BaseRepository[Category], ManagerLinkMixin):
    model = Category
    link_model = CategoryManager
    link_entity_attr = link_entity(CategoryManager.category_id)

    async def list_active(
        self, *, limit: int | None = None, offset: int = 0
    ) -> Sequence[Category]:
        """Активные категории (для меню бота)."""
        return await self.find(
            Category.is_active.is_(True),
            limit=limit,
            offset=offset,
            order_by=asc(Category.sort_order),
        )

    def point_condition(self, point_id: int):
        """Условие «привязана к точке ИЛИ глобальная» (без is_active)."""
        return point_visible_condition(
            Category.id,
            PointCategory,
            PointCategory.category_id,
            PointCategory.point_id,
            point_id,
        )

    async def list_active_for_point(
        self, point_id: int, *, limit: int | None = None, offset: int = 0
    ) -> Sequence[Category]:
        """Активные категории для точки: локальные ∪ глобальные."""
        return await self.find(
            Category.is_active.is_(True),
            self.point_condition(point_id),
            limit=limit,
            offset=offset,
            order_by=asc(Category.sort_order),
        )

    async def count_active_for_point(self, point_id: int) -> int:
        """Количество активных категорий для точки (total пагинации)."""
        return await self.count(
            Category.is_active.is_(True), self.point_condition(point_id)
        )

    async def global_ids(self, ids: Sequence[int]) -> set[int]:
        """Подмножество id без привязки к точкам (глобальные, для is_global)."""
        if not ids:
            return set()
        rows = await self.session.scalars(
            select(Category.id).where(
                Category.id.in_(ids),
                ~exists(select(1).where(PointCategory.category_id == Category.id)),
            )
        )
        return set(rows)

    async def list_manager_category_ids(self, user_id: int) -> list[int]:
        """Id категорий, доступных менеджеру: назначенные напрямую
        (category_managers) ∪ категории объектов с прямой связью
        (object_managers) — т.е. категории всех доступных объектов."""
        direct = await self.session.scalars(
            select(CategoryManager.category_id).where(
                CategoryManager.user_id == user_id
            )
        )
        via_objects = await self.session.scalars(
            select(Object.category_id)
            .join(ObjectManager, ObjectManager.object_id == Object.id)
            .where(ObjectManager.user_id == user_id)
        )
        return sorted(set(direct) | set(via_objects))
