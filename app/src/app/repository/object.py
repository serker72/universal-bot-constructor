"""Репозиторий объектов."""

from collections.abc import Sequence

from sqlalchemy import asc, exists, select
from sqlalchemy.orm import selectinload

from app.domain.models import Category, CategoryManager, Object, ObjectManager
from app.domain.models.point_object import PointObject
from app.repository.base import BaseRepository
from app.repository.manager_link import ManagerLinkMixin, link_entity
from app.repository.point_scope import point_visible_condition


class ObjectRepository(BaseRepository[Object], ManagerLinkMixin):
    """Объекты (CRUD) + связи с менеджерами (mixin).

    Методы доступа менеджеров (прямые ∪ через категорию) — единственная
    точка этой логики (используется API и ботом).
    """

    model = Object
    link_model = ObjectManager
    link_entity_attr = link_entity(ObjectManager.object_id)

    async def get_with_category(self, object_id: int) -> Object | None:
        """Объект по id вместе с категорией (eager-load, для бота)."""
        stmt = (
            select(Object)
            .options(selectinload(Object.category))
            .where(Object.id == object_id)
        )
        return (await self.session.scalars(stmt)).first()

    @staticmethod
    def active_conditions(category_id: int) -> list:
        """Условия «активный объект активной категории» (меню бота)."""
        return [
            Object.category_id == category_id,
            Object.is_active.is_(True),
            Object.category_id.in_(
                select(Category.id).where(Category.is_active.is_(True))
            ),
        ]

    @staticmethod
    def point_condition(point_id: int):
        """Условие «привязан к точке ИЛИ глобальный» (без is_active)."""
        return point_visible_condition(
            Object.id,
            PointObject,
            PointObject.object_id,
            PointObject.point_id,
            point_id,
        )

    def active_point_conditions(self, category_id: int, point_id: int) -> list:
        """Условия «активный объект активной категории, видимый точке»."""
        return [*self.active_conditions(category_id), self.point_condition(point_id)]

    async def list_by_category(
        self,
        category_id: int,
        *,
        only_active: bool = False,
        point_id: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Object]:
        """Объекты категории (для меню бота — только активные объекты
        активной категории; point_id — локальные ∪ глобальные)."""
        if only_active and point_id is not None:
            conditions = self.active_point_conditions(category_id, point_id)
        elif only_active:
            conditions = self.active_conditions(category_id)
        else:
            conditions = [Object.category_id == category_id]
        return await self.find(
            *conditions,
            limit=limit,
            offset=offset,
            order_by=asc(Object.sort_order),
        )

    async def is_visible_for_point(self, object_id: int, point_id: int) -> bool:
        """Видим ли объект для точки (привязан к ней ИЛИ глобальный)."""
        count = await self.count(
            Object.id == object_id,
            self.point_condition(point_id),
        )
        return count > 0

    async def global_ids(self, ids: Sequence[int]) -> set[int]:
        """Подмножество id без привязки к точкам (глобальные, для is_global)."""
        if not ids:
            return set()
        rows = await self.session.scalars(
            select(Object.id).where(
                Object.id.in_(ids),
                ~exists(select(1).where(PointObject.object_id == Object.id)),
            )
        )
        return set(rows)

    async def list_access_manager_ids(self, object_id: int) -> list[int]:
        """Id менеджеров с доступом к объекту: прямые связи ∪ менеджеры
        категории объекта (доступ через категорию)."""
        obj = await self.get(object_id)
        if obj is None:
            return []
        direct = await self.session.scalars(
            select(ObjectManager.user_id).where(
                ObjectManager.object_id == object_id
            )
        )
        via_category = await self.session.scalars(
            select(CategoryManager.user_id).where(
                CategoryManager.category_id == obj.category_id
            )
        )
        return sorted(set(direct) | set(via_category))

    async def list_manager_object_ids(self, user_id: int) -> list[int]:
        """Id объектов, доступных менеджеру: прямые связи (object_managers)
        ∪ объекты категорий менеджера (category_managers)."""
        direct = await self.session.scalars(
            select(ObjectManager.object_id).where(ObjectManager.user_id == user_id)
        )
        via_category = await self.session.scalars(
            select(Object.id)
            .join(
                CategoryManager,
                CategoryManager.category_id == Object.category_id,
            )
            .where(CategoryManager.user_id == user_id)
        )
        return sorted(set(direct) | set(via_category))
