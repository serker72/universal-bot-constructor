"""Репозиторий точек продаж (филиалов)."""

from collections.abc import Sequence

from sqlalchemy import asc

from app.domain.models import Point
from app.repository.base import BaseRepository


class PointRepository(BaseRepository[Point]):
    model = Point

    async def list_active(
        self, *, limit: int | None = None, offset: int = 0
    ) -> Sequence[Point]:
        """Активные точки (для селектора бота), по наименованию."""
        return await self.find(
            Point.is_active.is_(True),
            limit=limit,
            offset=offset,
            order_by=asc(Point.name),
        )

    async def count_active(self) -> int:
        """Количество активных точек."""
        return await self.count(Point.is_active.is_(True))

    async def get_active(self, point_id: int) -> Point | None:
        """Активная точка по id (неактивная — None, как несуществующая)."""
        return await self.find_one(Point.id == point_id, Point.is_active.is_(True))
