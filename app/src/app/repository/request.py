"""Репозиторий заявок."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.models import Request, RequestField, RequestStatus
from app.repository.base import BaseRepository

# Значения динамических полей вместе со справочником поля: сериализация
# RequestOut обращается к field.code/field.label, ленивая загрузка вне
# async-контекста даёт MissingGreenlet. Request.values — lazy="raise":
# значения загружаются только явно (один путь чтения).
_WITH_VALUES = selectinload(Request.values).selectinload(RequestField.field)


class RequestRepository(BaseRepository[Request]):
    model = Request

    async def get_with_values(
        self, pk: int, *, for_update: bool = False
    ) -> Request | None:
        """Заявка по id со значениями полей (и справочником полей).

        for_update=True — блокировка строки заявки (SELECT ... FOR UPDATE)
        до конца транзакции: смена статуса менеджером и отмена посетителем
        не перезаписывают друг друга.
        """
        stmt = select(Request).where(Request.id == pk).options(_WITH_VALUES)
        if for_update:
            stmt = stmt.with_for_update(of=Request).execution_options(
                populate_existing=True
            )
        return (await self.session.scalars(stmt)).first()

    async def get_for_update(self, pk: int) -> Request | None:
        """Заявка по id с блокировкой строки (без значений полей)."""
        stmt = (
            select(Request)
            .where(Request.id == pk)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).first()

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
            order_by=(Request.created_at.desc(), Request.id.desc()),
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
        date_to — исключающая граница (created_at < date_to).
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
            conditions.append(Request.created_at < date_to)

        stmt = (
            select(Request)
            .where(*conditions)
            .options(_WITH_VALUES)
            # id — tie-breaker: одинаковый created_at не даёт дублей/пропусков
            .order_by(Request.created_at.desc(), Request.id.desc())
        )
        items = (await self.session.scalars(stmt.limit(limit).offset(offset))).all()
        total = await self.count(*conditions)
        return items, total
