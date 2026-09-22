"""Тесты системных настроек (app.services.app_settings) на фейковом репозитории."""

import pytest

from app.services.app_settings import (
    DEFAULT_CANCEL_INTERVAL_HOURS,
    DEFAULT_CONSENT_TEXT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WELCOME_TEXT,
    KEY_CANCEL_INTERVAL_HOURS,
    KEY_CONSENT_TEXT,
    KEY_PAGE_SIZE,
    KEY_WELCOME_TEXT,
    AppSettingsService,
)


class FakeSettingRepository:
    """Заглушка репозитория настроек (значения в dict)."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.upserted: list[tuple[str, str]] = []

    async def get_value(self, key: str) -> str | None:
        return self.values.get(key)

    async def upsert(self, key: str, value: str) -> None:
        self.values[key] = value
        self.upserted.append((key, value))


@pytest.fixture
def repo() -> FakeSettingRepository:
    return FakeSettingRepository()


@pytest.fixture
def service(repo) -> AppSettingsService:
    return AppSettingsService(repo)  # type: ignore[arg-type]


async def test_defaults_when_empty(service: AppSettingsService):
    assert await service.get_page_size() == DEFAULT_PAGE_SIZE
    assert await service.get_cancel_interval_hours() == DEFAULT_CANCEL_INTERVAL_HOURS
    assert await service.get_consent_text() == DEFAULT_CONSENT_TEXT
    assert await service.get_welcome_text() == DEFAULT_WELCOME_TEXT


async def test_values_from_repo(service: AppSettingsService, repo):
    repo.values = {
        KEY_PAGE_SIZE: "5",
        KEY_CANCEL_INTERVAL_HOURS: "12",
        KEY_CONSENT_TEXT: "Согласие",
        KEY_WELCOME_TEXT: "Привет!",
    }
    assert await service.get_page_size() == 5
    assert await service.get_cancel_interval_hours() == 12
    assert await service.get_consent_text() == "Согласие"
    assert await service.get_welcome_text() == "Привет!"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc", DEFAULT_PAGE_SIZE),   # не число
        ("-1", DEFAULT_PAGE_SIZE),    # отрицательное
        ("0", DEFAULT_PAGE_SIZE),     # ноль недопустим
    ],
)
async def test_page_size_invalid_falls_back(service, raw, expected):
    service.repo.values = {KEY_PAGE_SIZE: raw}
    assert await service.get_page_size() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc", DEFAULT_CANCEL_INTERVAL_HOURS),
        ("-5", DEFAULT_CANCEL_INTERVAL_HOURS),
    ],
)
async def test_cancel_interval_invalid_falls_back(service, raw, expected):
    service.repo.values = {KEY_CANCEL_INTERVAL_HOURS: raw}
    assert await service.get_cancel_interval_hours() == expected


async def test_cancel_interval_zero_is_valid(service, repo):
    repo.values = {KEY_CANCEL_INTERVAL_HOURS: "0"}
    assert await service.get_cancel_interval_hours() == 0


async def test_set_delegates_to_repo(service: AppSettingsService, repo):
    await service.set(KEY_WELCOME_TEXT, "Новый текст")
    assert repo.upserted == [(KEY_WELCOME_TEXT, "Новый текст")]
    assert await service.get_welcome_text() == "Новый текст"
