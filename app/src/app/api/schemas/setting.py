"""Схемы настроек."""

from pydantic import BaseModel


class SettingsOut(BaseModel):
    """Все настройки системы."""

    settings: dict[str, str]


class SettingsIn(BaseModel):
    """Обновление настроек (частично)."""

    settings: dict[str, str]
