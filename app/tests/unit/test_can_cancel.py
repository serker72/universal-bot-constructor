"""Тесты логики отмены заявок (BotService.can_cancel) на моках настроек.

Без БД: AppSettingsService — на фейковом репозитории, Request —
объект домена, собранный напрямую (в can_cancel сессия не используется).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot.services import BotService
from app.domain.models import Request, RequestStatus
from app.services.app_settings import (
    DEFAULT_CANCEL_INTERVAL_HOURS,
    KEY_CANCEL_INTERVAL_HOURS,
    AppSettingsService,
)


class FakeSettingRepository:
    """Заглушка репозитория настроек (значения в dict)."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def get_value(self, key: str) -> str | None:
        return self.values.get(key)

    async def upsert(self, key: str, value: str) -> None:
        self.values[key] = value


def make_service(interval_hours: str) -> BotService:
    """BotService с настройкой интервала отмены (остальное — заглушки)."""
    settings = AppSettingsService(
        FakeSettingRepository({KEY_CANCEL_INTERVAL_HOURS: interval_hours})
    )
    return BotService(
        session=None,  # type: ignore[arg-type]
        visitors=None,  # type: ignore[arg-type]
        categories=None,  # type: ignore[arg-type]
        objects=None,  # type: ignore[arg-type]
        requests=None,  # type: ignore[arg-type]
        request_fields=None,  # type: ignore[arg-type]
        app_settings=settings,
        publisher=None,  # type: ignore[arg-type]
    )


def make_request(
    status: RequestStatus, confirmed_at: datetime | None = None
) -> Request:
    return Request(
        visitor_id=1,
        object_id=1,
        phone="+79001234567",
        status=status,
        confirmed_at=confirmed_at,
    )


NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def service() -> BotService:
    return make_service("24")


@pytest.fixture(autouse=True)
def _freeze_now(monkeypatch):
    """Фиксируем «сейчас» для проверки границ интервала."""
    import app.bot.services as services_mod

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(services_mod, "datetime", _FixedDatetime)


# --- статусы ---------------------------------------------------------------


async def test_new_always_cancelable(service):
    assert await service.can_cancel(make_request(RequestStatus.NEW))


async def test_rejected_not_cancelable(service):
    assert not await service.can_cancel(make_request(RequestStatus.REJECTED))


async def test_completed_not_cancelable(service):
    assert not await service.can_cancel(make_request(RequestStatus.COMPLETED))


async def test_already_cancelled_not_cancelable(service):
    assert not await service.can_cancel(
        make_request(RequestStatus.CANCELLED_BY_CUSTOMER)
    )


# --- approved + интервал ----------------------------------------------------


async def test_approved_within_interval_cancelable(service):
    req = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(hours=23)
    )
    assert await service.can_cancel(req)


async def test_approved_interval_expired_not_cancelable(service):
    req = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(hours=25)
    )
    assert not await service.can_cancel(req)


async def test_approved_without_confirmed_at_not_cancelable(service):
    # подтверждена, но время подтверждения не зафиксировано — нельзя
    req = make_request(RequestStatus.APPROVED, confirmed_at=None)
    assert not await service.can_cancel(req)


async def test_approved_exactly_on_deadline_cancelable(service):
    # граница: now == confirmed_at + интервал → ещё можно
    req = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(hours=24)
    )
    assert await service.can_cancel(req)


# --- интервал из настроек ---------------------------------------------------


async def test_interval_zero_disables_cancel():
    svc = make_service("0")
    req = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(minutes=1)
    )
    assert not await svc.can_cancel(req)


async def test_interval_from_settings():
    # интервал 2 часа: подтверждена час назад — можно, три часа — нельзя
    svc = make_service("2")
    fresh = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(hours=1)
    )
    stale = make_request(
        RequestStatus.APPROVED, confirmed_at=NOW - timedelta(hours=3)
    )
    assert await svc.can_cancel(fresh)
    assert not await svc.can_cancel(stale)


async def test_default_interval_when_not_set():
    svc = make_service("x-invalid")  # невалидное значение → дефолт 24
    req = make_request(
        RequestStatus.APPROVED,
        confirmed_at=NOW - timedelta(hours=DEFAULT_CANCEL_INTERVAL_HOURS - 1),
    )
    assert await svc.can_cancel(req)
