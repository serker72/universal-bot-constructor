"""Часовые пояса точек продаж для интерфейса бота.

Вся логика — на IANA-идентификаторах (`zoneinfo`, stdlib + tzdata);
русские наименования (`TZ_RU`) используются только для отображения.

Неизвестная/пустая зона не приводит к падению: подставляется
`DEFAULT_TZ` (Europe/Moscow), а имя в тексте отдаётся как есть —
данные могли быть заведены до появления валидации в API.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Europe/Moscow"

# Русские наименования используемых зон (отображение в боте)
TZ_RU: dict[str, str] = {
    "Europe/Kaliningrad": "Европа/Калининград",
    "Europe/Moscow": "Европа/Москва",
    "Europe/Samara": "Европа/Самара",
    "Asia/Yekaterinburg": "Азия/Екатеринбург",
    "Asia/Omsk": "Азия/Омск",
    "Asia/Krasnoyarsk": "Азия/Красноярск",
    "Asia/Irkutsk": "Азия/Иркутск",
    "Asia/Yakutsk": "Азия/Якутск",
    "Asia/Vladivostok": "Азия/Владивосток",
    "Asia/Magadan": "Азия/Магадан",
    "Asia/Kamchatka": "Азия/Камчатка",
}


def zone_of(tz_name: str | None) -> ZoneInfo:
    """ZoneInfo по IANA-имени; неизвестная/пустая — DEFAULT_TZ (без падения)."""
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo(DEFAULT_TZ)


def utc_offset_label(tz_name: str | None, now: datetime | None = None) -> str:
    """Смещение зоны: «UTC+5», «UTC+5:30», «UTC-3» (по текущему моменту)."""
    zone = zone_of(tz_name)
    moment = now if now is not None else datetime.now(zone)
    offset = moment.astimezone(zone).utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds()) // 60
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    label = f"UTC{sign}{hours}"
    return f"{label}:{minutes:02d}" if minutes else label


def format_timezone(tz_name: str | None) -> str:
    """Строка таймзоны для интерфейса: «Азия/Екатеринбург, UTC+5».

    Неизвестная IANA-зона — имя отдаётся как есть + посчитанное смещение.
    """
    name = tz_name or DEFAULT_TZ
    label = TZ_RU.get(name, name)
    return f"{label}, {utc_offset_label(name)}"


def today_in(tz_name: str | None) -> date:
    """Сегодняшняя дата по таймзоне точки (контейнер работает в UTC)."""
    return datetime.now(zone_of(tz_name)).date()
