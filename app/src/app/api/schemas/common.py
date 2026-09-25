"""Общие схемы (пагинация)."""

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

ItemT = TypeVar("ItemT")

# Верхняя граница размера страницы списков API (защита от выгрузки всей таблицы
# одним запросом); справочники frontend дочитывает постранично
MAX_PAGE_LIMIT = 100

# Параметры пагинации list-эндпоинтов (422 при выходе за границы)
LimitQuery = Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)]
OffsetQuery = Annotated[int, Query(ge=0)]


class Page(BaseModel, Generic[ItemT]):
    """Страница результатов."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int
