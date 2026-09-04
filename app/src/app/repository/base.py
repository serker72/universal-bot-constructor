"""Базовый репозиторий SQLAlchemy (async).

Конкретные репозитории наследуются и задают атрибут `model`.
Сессия передаётся снаружи (управляется DI, см. app/di/db.py).
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnExpressionArgument, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Типовые операции CRUD над одной моделью."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, pk: Any) -> ModelT | None:
        """Получить объект по первичному ключу."""
        return await self.session.get(self.model, pk)

    async def find_one(self, *conditions: ColumnExpressionArgument[bool]) -> ModelT | None:
        """Найти один объект по условиям."""
        stmt = select(self.model).where(*conditions).limit(1)
        return (await self.session.scalars(stmt)).first()

    async def find(
        self,
        *conditions: ColumnExpressionArgument[bool],
        limit: int | None = None,
        offset: int = 0,
        order_by: ColumnExpressionArgument[Any] | None = None,
    ) -> Sequence[ModelT]:
        """Список объектов по условиям с пагинацией и сортировкой."""
        stmt = select(self.model).where(*conditions)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        stmt = stmt.offset(offset)
        return (await self.session.scalars(stmt)).all()

    async def count(self, *conditions: ColumnExpressionArgument[bool]) -> int:
        """Количество объектов по условиям."""
        stmt = select(func.count()).select_from(self.model).where(*conditions)
        return (await self.session.execute(stmt)).scalar_one()

    async def add(self, obj: ModelT) -> ModelT:
        """Добавить объект и выполнить flush (id и server defaults заполняются)."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        """Удалить объект."""
        await self.session.delete(obj)
