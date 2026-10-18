"""Репозиторий точек продаж (филиалов)."""

from collections.abc import Sequence

from sqlalchemy import asc, delete, select

from app.domain.models import Point
from app.domain.models.point_category import PointCategory
from app.domain.models.point_object import PointObject
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

    # -- привязки категорий/объектов (PUT /points/{id}/categories|objects) ----

    async def list_category_ids(self, point_id: int) -> list[int]:
        """Id категорий, привязанных к точке."""
        rows = await self.session.scalars(
            select(PointCategory.category_id).where(
                PointCategory.point_id == point_id
            )
        )
        return sorted(rows)

    async def list_object_ids(self, point_id: int) -> list[int]:
        """Id объектов, привязанных к точке."""
        rows = await self.session.scalars(
            select(PointObject.object_id).where(PointObject.point_id == point_id)
        )
        return sorted(rows)

    async def sync_categories(self, point_id: int, target: set[int]) -> None:
        """Заменить набор категорий точки (diff: DELETE лишних + INSERT новых)."""
        await self._sync_links(
            PointCategory,
            PointCategory.category_id,
            point_id,
            target,
            current=set(await self.list_category_ids(point_id)),
        )

    async def sync_objects(self, point_id: int, target: set[int]) -> None:
        """Заменить набор объектов точки (diff, см. sync_categories)."""
        await self._sync_links(
            PointObject,
            PointObject.object_id,
            point_id,
            target,
            current=set(await self.list_object_ids(point_id)),
        )

    async def _sync_links(
        self,
        link_model,
        link_entity_attr,
        point_id: int,
        target: set[int],
        *,
        current: set[int],
    ) -> None:
        """Общая diff-замена связей точки (pattern sync_managers)."""
        to_remove = current - target
        if to_remove:
            await self.session.execute(
                delete(link_model).where(
                    link_model.point_id == point_id,
                    link_entity_attr.in_(to_remove),
                )
            )
        for entity_id in target - current:
            self.session.add(link_model(point_id=point_id, **{
                link_entity_attr.key: entity_id
            }))
        await self.session.flush()
