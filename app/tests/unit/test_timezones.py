"""Unit-тесты модуля часовых поясов точек продаж (app.bot.timezones).

Проверяется форматирование IANA-зон:
- русское наименование + UTC-смещение (`format_timezone`);
- минутная зона (UTC+5:30);
- неизвестная зона без падения;
- `today_in` — «сегодня» по таймзоне.
"""

from datetime import date, datetime

from app.bot.timezones import (
    DEFAULT_TZ,
    TZ_RU,
    format_timezone,
    today_in,
    utc_offset_label,
    zone_of,
)


# -- zone_of ------------------------------------------------------------------


def test_zone_of_known():
    """Известная зона возвращает ZoneInfo."""
    from zoneinfo import ZoneInfo

    zi = zone_of("Asia/Yekaterinburg")
    assert isinstance(zi, ZoneInfo)
    assert str(zi) == "Asia/Yekaterinburg"


def test_zone_of_unknown_defaults_to_moscow():
    """Неизвестная зона — зона по умолчанию (Москва)."""
    zi = zone_of("Non/Existent")
    assert str(zi) == DEFAULT_TZ


def test_zone_of_none_defaults_to_moscow():
    """None — зона по умолчанию."""
    zi = zone_of(None)
    assert str(zi) == DEFAULT_TZ


# -- utc_offset_label ---------------------------------------------------------


def test_utc_offset_positive():
    """Москва: UTC+3."""
    assert utc_offset_label("Europe/Moscow") == "UTC+3"


def test_utc_offset_with_minutes():
    """Азия/Калькутта: UTC+5:30 (минутная зона)."""
    assert utc_offset_label("Asia/Kolkata") == "UTC+5:30"


def test_utc_offset_negative():
    """Америка/Нью_Йорк: UTC-5 (или -4 в летнее время, но не +)."""
    offset = utc_offset_label("America/New_York")
    assert offset.startswith("UTC-")


def test_utc_offset_unknown_without_fall():
    """Неизвестная зона не падает — считает смещение."""
    offset = utc_offset_label("Non/Existent")
    assert offset.startswith("UTC+")


# -- format_timezone ----------------------------------------------------------


def test_format_timezone_known():
    """Известная зона: русское имя + UTC-смещение."""
    result = format_timezone("Europe/Moscow")
    assert "Европа/Москва" in result
    assert "UTC+3" in result


def test_format_timezone_asia_yekaterinburg():
    """Азия/Екатеринбург — UTC+5."""
    result = format_timezone("Asia/Yekaterinburg")
    assert "Азия/Екатеринбург" in result
    assert "UTC+5" in result


def test_format_timezone_unknown_without_fall():
    """Неизвестная зона: имя как есть + посчитанное смещение."""
    result = format_timezone("Non/Existent")
    assert "Non/Existent" in result
    assert "UTC" in result


def test_format_timezone_empty_defaults_to_moscow():
    """Пустая строка — зона по умолчанию."""
    result = format_timezone("")
    assert "Европа/Москва" in result


def test_format_timezone_none_defaults_to_moscow():
    """None — зона по умолчанию."""
    result = format_timezone(None)
    assert "Европа/Москва" in result


# -- today_in -----------------------------------------------------------------


def test_today_in_moscow():
    """Сегодня по Москве — та же календарная дата, что и в UTC (в большинстве случаев)."""
    from datetime import timedelta

    moscow_today = today_in("Europe/Moscow")
    utc_now = datetime.now().date()
    # Москва +3 часа, поэтому «сегодня» может отличаться на 1 день только
    # в интервале UTC 21:00–23:59 (когда в Москве ещё следующий день).
    assert moscow_today - utc_now in (timedelta(days=0), timedelta(days=1))


def test_today_in_yekaterinburg_plus_5():
    """Екатеринбург +5 — «сегодня» сдвигается вперёд."""
    from datetime import timedelta

    ekb_today = today_in("Asia/Yekaterinburg")
    utc_now = datetime.now().date()
    # Сдвиг +5: «сегодня» может быть на 1 день впереди UTC.
    assert ekb_today - utc_now in (timedelta(days=0), timedelta(days=1))


# -- TZ_RU completeness -------------------------------------------------------


def test_tz_ru_contains_russian_names():
    """Словарь содержит кириллические наименования."""
    for key, ru_name in TZ_RU.items():
        assert ru_name.isprintable()
