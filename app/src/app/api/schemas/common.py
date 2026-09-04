"""Общие схемы (пагинация)."""

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """Страница результатов."""

    items: list[ItemT]
    total: int
    limit: int
    offset: int
