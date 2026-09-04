"""Репозиторий настроек (ключ-значение)."""

from app.domain.models import Setting
from app.repository.base import BaseRepository


class SettingRepository(BaseRepository[Setting]):
    model = Setting

    async def get_value(self, key: str) -> str | None:
        """Значение настройки по ключу (None — не задана)."""
        setting = await self.get(key)
        return setting.value if setting is not None else None

    async def upsert(self, key: str, value: str) -> Setting:
        """Создать или обновить настройку."""
        setting = await self.get(key)
        if setting is None:
            setting = Setting(key=key, value=value)
            await self.add(setting)
        else:
            setting.value = value
        return setting

    async def get_all(self) -> dict[str, str]:
        """Все настройки в виде словаря."""
        settings = await self.find()
        return {s.key: s.value for s in settings}
