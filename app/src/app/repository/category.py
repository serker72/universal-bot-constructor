"""Репозиторий категорий."""

from collections.abc import Sequence

from sqlalchemy import asc, select

from app.domain.models import Category, CategoryManager
from app.repository.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

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

    async def add_manager(self, category_id: int, user_id: int) -> CategoryManager:
        """Назначить менеджера на категорию."""
        link = CategoryManager(category_id=category_id, user_id=user_id)
        self.session.add(link)
        return link

    async def remove_manager(self, category_id: int, user_id: int) -> None:
        """Снять менеджера с категории."""
        link = (
            await self.session.scalars(
                select(CategoryManager).where(
                    CategoryManager.category_id == category_id,
                    CategoryManager.user_id == user_id,
                )
            )
        ).first()
        if link is not None:
            await self.session.delete(link)

    async def list_manager_ids(self, category_id: int) -> list[int]:
        """Id менеджеров, назначенных на категорию."""
        links = await self.session.scalars(
            select(CategoryManager.user_id).where(
                CategoryManager.category_id == category_id
            )
        )
        return list(links)
