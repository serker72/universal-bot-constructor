"""Репозиторий посетителей."""

from collections.abc import Sequence

from sqlalchemy import select

from app.domain.models import Visitor
from app.repository.base import BaseRepository


class VisitorRepository(BaseRepository[Visitor]):
    model = Visitor

    async def get_by_telegram_id(self, telegram_id: int) -> Visitor | None:
        """Посетитель по telegram_id."""
        return await self.find_one(Visitor.telegram_id == telegram_id)

    async def list_page(
        self,
        *,
        search: str | None = None,
        is_blocked: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Visitor], int]:
        """Страница посетителей с поиском по ФИО и фильтром блокировки."""
        conditions = []
        if search:
            conditions.append(Visitor.full_name.ilike(f"%{search}%"))
        if is_blocked is not None:
            conditions.append(Visitor.is_blocked == is_blocked)

        stmt = select(Visitor).where(*conditions).order_by(Visitor.id)
        items = (await self.session.scalars(stmt.limit(limit).offset(offset))).all()
        total = await self.count(*conditions)
        return items, total
