"""Схемы пользователей."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import UserRole


class UserIn(BaseModel):
    """Создание пользователя."""

    username: str = Field(min_length=3, max_length=255)
    # политика (длина в символах и байтах, частые пароли) — validate_password_policy;
    # max_length в символах с запасом: байтовый лимит bcrypt (72) проверяется отдельно
    password: str = Field(min_length=10, max_length=72)
    role: UserRole = UserRole.MANAGER
    telegram_id: int | None = None
    is_active: bool = True


class UserUpdateIn(BaseModel):
    """Редактирование пользователя (все поля опциональны).

    ``telegram_id``: ключ не передан — не менять, ``null`` — очистить.
    """

    password: str | None = Field(default=None, min_length=10, max_length=72)
    role: UserRole | None = None
    telegram_id: int | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    """Пользователь (без хеша пароля)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    telegram_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
