"""Схемы аутентификации."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import UserRole


class LoginIn(BaseModel):
    """Вход с указанием устройства (thumbmarkjs)."""

    # ограничения длины: username попадает в ключ rate-limit Redis,
    # пароль bcrypt всё равно учитывает только первые 72 байта
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)
    device_id: str = Field(min_length=8, max_length=255)


class LoginOut(BaseModel):
    """Данные пользователя после входа (токены — в httpOnly cookies)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
