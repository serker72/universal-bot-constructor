"""Репозиторий объектов."""

from collections.abc import Sequence

from sqlalchemy import asc, select

from app.domain.models import Object, ObjectManager
from app.repository.base import BaseRepository


class ObjectRepository(BaseRepository[Object]):
    model = Object

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

    async def get_with_managers(self, pk: int) -> Object | None:
        """Объект вместе с назначенными менеджерами."""
        obj = await self.get(pk)
        if obj is not None:
            await self.session.refresh(obj, ["managers"])
        return obj

    async def add_manager(self, object_id: int, user_id: int) -> ObjectManager:
        """Назначить менеджера на объект."""
        link = ObjectManager(object_id=object_id, user_id=user_id)
        self.session.add(link)
        return link

    async def remove_manager(self, object_id: int, user_id: int) -> None:
        """Снять менеджера с объекта."""
        # ВАЖНО: не self.find_one() — он ищет self.model (Object),
        # а здесь нужна связь ObjectManager
        link = (
            await self.session.scalars(
                select(ObjectManager).where(
                    ObjectManager.object_id == object_id,
                    ObjectManager.user_id == user_id,
                )
            )
        ).first()
        if link is not None:
            await self.session.delete(link)

    async def list_manager_ids(self, object_id: int) -> list[int]:
        """Id менеджеров, назначенных на объект."""
        links = await self.session.scalars(
            select(ObjectManager.user_id).where(ObjectManager.object_id == object_id)
        )
        return list(links)
