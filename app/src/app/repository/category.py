"""Репозиторий категорий."""

from collections.abc import Sequence

from sqlalchemy import asc

from app.domain.models import Category, CategoryManager
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
