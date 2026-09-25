"""Схемы объектов и назначения менеджеров."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Лимит Telegram на текст сообщения — 4096 символов; карточка объекта =
# название (до 255) + описание, с запасом под HTML-разметку и санитизацию
SHORT_DESCRIPTION_MAX_LENGTH = 3500


class ObjectIn(BaseModel):
    """Создание объекта (все поля обязательны, кроме опциональных)."""

    category_id: int
    name: str = Field(min_length=1, max_length=255)
    short_description: str = Field(default="", max_length=SHORT_DESCRIPTION_MAX_LENGTH)
    sort_order: int = 0
    is_active: bool = True


class ObjectUpdateIn(BaseModel):
    """Обновление объекта (PATCH: все поля опциональны)."""

    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_description: str | None = Field(
        default=None, max_length=SHORT_DESCRIPTION_MAX_LENGTH
    )
    sort_order: int | None = None
    is_active: bool | None = None


class ObjectOut(BaseModel):
    """Объект (pdf_path не раскрывается — доступ через /pdf)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    short_description: str
    sort_order: int
    is_active: bool
    has_pdf: bool = False  # вычисляется из pdf_path
    created_at: datetime
    updated_at: datetime


class ObjectManagersIn(BaseModel):
    """Замена списка менеджеров объекта."""

    user_ids: list[int]


class ObjectManagersOut(BaseModel):
    """Список id менеджеров объекта."""

    object_id: int
    user_ids: list[int]
