"""Репозиторий объектов."""

from collections.abc import Sequence

from sqlalchemy import asc, select
from sqlalchemy.orm import selectinload

from app.domain.models import CategoryManager, Object, ObjectManager
from app.repository.base import BaseRepository
from app.repository.manager_link import ManagerLinkMixin, link_entity


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

    async def list_by_category(
        self,
        category_id: int,
        *,
        only_active: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Object]:
        """Объекты категории (для меню бота — только активные)."""
        conditions = [Object.category_id == category_id]
        if only_active:
            conditions.append(Object.is_active.is_(True))
        return await self.find(
            *conditions,
            limit=limit,
            offset=offset,
            order_by=asc(Object.sort_order),
        )

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
