"""Сервис системных настроек (таблица settings).

Типизированный доступ к настройкам с значениями по умолчанию:
- размер страницы меню бота (по умолчанию 10);
- интервал отмены подтверждённой заявки в минутах (по умолчанию 1440 = 24 ч);
- текст согласия на обработку персональных данных;
- текст приветствия бота.
"""

from app.repository.setting import SettingRepository

KEY_PAGE_SIZE = "bot.page_size"
KEY_CANCEL_INTERVAL_MINUTES = "requests.cancel_interval_minutes"
KEY_CONSENT_TEXT = "bot.consent_text"
KEY_WELCOME_TEXT = "bot.welcome_text"

DEFAULT_PAGE_SIZE = 10
DEFAULT_CANCEL_INTERVAL_MINUTES = 24 * 60
DEFAULT_CONSENT_TEXT = (
    "Я даю согласие на обработку моих персональных данных "
    "(ФИО, номер телефона) в целях обработки заявок."
)
DEFAULT_WELCOME_TEXT = "Добро пожаловать!"


class AppSettingsService:
    """Чтение и запись системных настроек."""

    def __init__(self, repo: SettingRepository) -> None:
        self.repo = repo

    async def get_page_size(self) -> int:
        """Размер страницы пагинации меню бота."""
        raw = await self.repo.get_value(KEY_PAGE_SIZE)
        try:
            value = int(raw) if raw is not None else DEFAULT_PAGE_SIZE
        except ValueError:
            return DEFAULT_PAGE_SIZE
        return value if value > 0 else DEFAULT_PAGE_SIZE

    async def get_cancel_interval_minutes(self) -> int:
        """Интервал отмены подтверждённой заявки, минуты."""
        raw = await self.repo.get_value(KEY_CANCEL_INTERVAL_MINUTES)
        try:
            value = int(raw) if raw is not None else DEFAULT_CANCEL_INTERVAL_MINUTES
        except ValueError:
            return DEFAULT_CANCEL_INTERVAL_MINUTES
        return value if value >= 0 else DEFAULT_CANCEL_INTERVAL_MINUTES

    async def get_consent_text(self) -> str:
        """Текст согласия на обработку персональных данных."""
        return (
            await self.repo.get_value(KEY_CONSENT_TEXT) or DEFAULT_CONSENT_TEXT
        )

    async def get_welcome_text(self) -> str:
        """Текст приветствия бота."""
        return (
            await self.repo.get_value(KEY_WELCOME_TEXT) or DEFAULT_WELCOME_TEXT
        )

    async def set(self, key: str, value: str) -> None:
        """Сохранить значение настройки."""
        await self.repo.upsert(key, value)
