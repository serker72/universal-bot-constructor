"""Сервис системных настроек (таблица settings).

Типизированный доступ к настройкам с значениями по умолчанию:
- размер страницы меню бота (по умолчанию 10);
- интервал отмены подтверждённой заявки в часах (по умолчанию 24);
- текст согласия на обработку персональных данных;
- текст приветствия бота;
- флаги сценария заявки: использование времени и даты окончания.
"""

from app.repository.setting import SettingRepository

KEY_PAGE_SIZE = "bot.page_size"
KEY_CANCEL_INTERVAL_HOURS = "requests.cancel_interval_hours"
KEY_CONSENT_TEXT = "bot.consent_text"
KEY_WELCOME_TEXT = "bot.welcome_text"
KEY_IS_USE_TIME_IN_REQUEST = "requests.is_use_time_in_request"
KEY_IS_USE_END_DATE_IN_REQUEST = "requests.is_use_end_date_in_request"

DEFAULT_PAGE_SIZE = 10
DEFAULT_CANCEL_INTERVAL_HOURS = 24
DEFAULT_CONSENT_TEXT = (
    "Я даю согласие на обработку моих персональных данных "
    "(ФИО, номер телефона) в целях обработки заявок."
)
DEFAULT_WELCOME_TEXT = "Добро пожаловать!"
DEFAULT_IS_USE_TIME_IN_REQUEST = False
DEFAULT_IS_USE_END_DATE_IN_REQUEST = False

TRUE_VALUES = {"1", "true", "yes", "on", "да", "истина"}


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

    async def get_cancel_interval_hours(self) -> int:
        """Интервал отмены подтверждённой заявки, часы."""
        raw = await self.repo.get_value(KEY_CANCEL_INTERVAL_HOURS)
        try:
            value = int(raw) if raw is not None else DEFAULT_CANCEL_INTERVAL_HOURS
        except ValueError:
            return DEFAULT_CANCEL_INTERVAL_HOURS
        return value if value >= 0 else DEFAULT_CANCEL_INTERVAL_HOURS

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

    async def _get_bool(self, key: str, default: bool) -> bool:
        """Прочитать булеву настройку (неразличимые значения → default)."""
        raw = await self.repo.get_value(key)
        if raw is None:
            return default
        return raw.strip().lower() in TRUE_VALUES

    async def get_is_use_time_in_request(self) -> bool:
        """Флаг: использовать время в запросе (окна выбора часов/минут)."""
        return await self._get_bool(
            KEY_IS_USE_TIME_IN_REQUEST, DEFAULT_IS_USE_TIME_IN_REQUEST
        )

    async def get_is_use_end_date_in_request(self) -> bool:
        """Флаг: использовать дату окончания в запросе (окна конечной даты/времени)."""
        return await self._get_bool(
            KEY_IS_USE_END_DATE_IN_REQUEST, DEFAULT_IS_USE_END_DATE_IN_REQUEST
        )

    async def set(self, key: str, value: str) -> None:
        """Сохранить значение настройки."""
        await self.repo.upsert(key, value)
