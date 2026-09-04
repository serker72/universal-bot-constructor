"""Репозиторий категорий."""

from collections.abc import Sequence

from sqlalchemy import asc

from app.domain.models import Category
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
