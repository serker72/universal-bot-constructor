"""Сервис системных настроек (таблица settings).

Типизированный доступ к настройкам с значениями по умолчанию:
- размер страницы меню бота (по умолчанию 10, 1..MAX_PAGE_SIZE);
- интервал отмены подтверждённой заявки в минутах (по умолчанию 1440 = 24 ч);
- текст согласия на обработку персональных данных;
- текст приветствия бота (пустая строка — приветствие отключено).

Значения кешируются в процессе на CACHE_TTL_SECONDS (бот читает настройки
на каждое обновление); запись через set() сбрасывает кеш процесса.
"""

import time

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

# Границы значений (валидация PUT /settings и чтения)
# 50 кнопок + пагинация + навигация — в пределах лимита клавиатуры Telegram (100)
MAX_PAGE_SIZE = 50
MAX_CANCEL_INTERVAL_MINUTES = 365 * 24 * 60
# Лимит Telegram на текст сообщения — 4096 символов (с запасом под разметку)
MAX_TEXT_LENGTH = 3500

CACHE_TTL_SECONDS = 30

# Кеш значений процесса: key -> (значение или None, время чтения)
_cache: dict[str, tuple[str | None, float]] = {}


def clear_cache() -> None:
    """Сбросить кеш настроек процесса."""
    _cache.clear()


class AppSettingsService:
    """Чтение и запись системных настроек."""

    def __init__(self, repo: SettingRepository) -> None:
        self.repo = repo

    async def _get(self, key: str) -> str | None:
        """Значение настройки с кешированием на CACHE_TTL_SECONDS."""
        cached = _cache.get(key)
        now = time.monotonic()
        if cached is not None and now - cached[1] < CACHE_TTL_SECONDS:
            return cached[0]
        value = await self.repo.get_value(key)
        _cache[key] = (value, now)
        return value

    async def get_page_size(self) -> int:
        """Размер страницы пагинации меню бота."""
        raw = await self._get(KEY_PAGE_SIZE)
        try:
            value = int(raw) if raw is not None else DEFAULT_PAGE_SIZE
        except ValueError:
            return DEFAULT_PAGE_SIZE
        return value if 0 < value <= MAX_PAGE_SIZE else DEFAULT_PAGE_SIZE

    async def get_cancel_interval_minutes(self) -> int:
        """Интервал отмены подтверждённой заявки, минуты."""
        raw = await self._get(KEY_CANCEL_INTERVAL_MINUTES)
        try:
            value = int(raw) if raw is not None else DEFAULT_CANCEL_INTERVAL_MINUTES
        except ValueError:
            return DEFAULT_CANCEL_INTERVAL_MINUTES
        return value if value >= 0 else DEFAULT_CANCEL_INTERVAL_MINUTES

    async def get_consent_text(self) -> str:
        """Текст согласия на обработку персональных данных (пусто — по умолчанию)."""
        return await self._get(KEY_CONSENT_TEXT) or DEFAULT_CONSENT_TEXT

    async def get_welcome_text(self) -> str:
        """Текст приветствия бота.

        Ключ не задан — текст по умолчанию; пустая строка — приветствие отключено.
        """
        value = await self._get(KEY_WELCOME_TEXT)
        return DEFAULT_WELCOME_TEXT if value is None else value

    async def set(self, key: str, value: str) -> None:
        """Сохранить значение настройки."""
        await self.repo.upsert(key, value)
        _cache.pop(key, None)


def validate_setting(key: str, value: str) -> str:
    """Проверить и нормализовать значение настройки (ValueError — с текстом ошибки)."""
    if key == KEY_PAGE_SIZE:
        number = _parse_int(value, key)
        if not 1 <= number <= MAX_PAGE_SIZE:
            raise ValueError(f"{key}: целое число 1..{MAX_PAGE_SIZE}")
        return str(number)
    if key == KEY_CANCEL_INTERVAL_MINUTES:
        number = _parse_int(value, key)
        if not 0 <= number <= MAX_CANCEL_INTERVAL_MINUTES:
            raise ValueError(f"{key}: целое число 0..{MAX_CANCEL_INTERVAL_MINUTES}")
        return str(number)
    if key in (KEY_CONSENT_TEXT, KEY_WELCOME_TEXT):
        if len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"{key}: не длиннее {MAX_TEXT_LENGTH} символов")
        return value
    return value


def _parse_int(value: str, key: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        raise ValueError(f"{key}: ожидается целое число") from None
