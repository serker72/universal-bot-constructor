"""Репозиторий заявок."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.domain.models import ObjectManager, Request, RequestStatus
from app.repository.base import BaseRepository


class RequestRepository(BaseRepository[Request]):
    model = Request

    async def list_by_visitor(
        self,
        visitor_id: int,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Request]:
        """Заявки посетителя (для бота, «Мои заявки»)."""
        return await self.find(
            Request.visitor_id == visitor_id,
            limit=limit,
            offset=offset,
            order_by=Request.created_at.desc(),
        )

    async def list_page(
        self,
        *,
        object_ids: list[int] | None = None,
        status: RequestStatus | None = None,
        object_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Request], int]:
        """Страница заявок с фильтрами.

        object_ids=None — все объекты (admin);
        пустой список — у менеджера нет объектов, вернуть пусто.
        """
        conditions = []
        if object_ids is not None:
            if not object_ids:
                return [], 0
            conditions.append(Request.object_id.in_(object_ids))
        if object_id is not None:
            conditions.append(Request.object_id == object_id)
        if status is not None:
            conditions.append(Request.status == status)
        if date_from is not None:
            conditions.append(Request.created_at >= date_from)
        if date_to is not None:
            conditions.append(Request.created_at <= date_to)

        stmt = select(Request).where(*conditions).order_by(Request.created_at.desc())
        items = (await self.session.scalars(stmt.limit(limit).offset(offset))).all()
        total = await self.count(*conditions)
        return items, total

    async def list_manager_object_ids(self, user_id: int) -> list[int]:
        """Id объектов, назначенных менеджеру."""
        links = await self.session.scalars(
            select(ObjectManager.object_id).where(ObjectManager.user_id == user_id)
        )
        return list(links)
