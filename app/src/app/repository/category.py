"""Репозиторий категорий."""

from collections.abc import Sequence

from sqlalchemy import asc, select

from app.domain.models import Category, CategoryManager, Object, ObjectManager
from app.repository.base import BaseRepository
from app.repository.manager_link import ManagerLinkMixin, link_entity


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
