"""Тесты русифицированного календаря (app.bot.widgets.ru_calendar)."""

from datetime import date

from aiogram_dialog.widgets.kbd import CalendarConfig, CalendarScope

from app.bot.widgets.ru_calendar import (
    RU_MONTHS,
    RU_WEEKDAYS,
    RuCalendar,
    RuDaysHeaderText,
    RuMonthText,
    RuWeekdayText,
)


async def test_month_text_by_month_key():
    text = RuMonthText()
    assert await text.render_text({"month": 1}, None) == "Январь"
    assert await text.render_text({"month": 9}, None) == "Сентябрь"
    assert await text.render_text({"month": 12}, None) == "Декабрь"


async def test_month_text_by_date():
    text = RuMonthText()
    assert await text.render_text({"date": date(2026, 9, 17)}, None) == "Сентябрь"


async def test_weekday_text():
    text = RuWeekdayText()
    assert await text.render_text({"week_day": 1}, None) == "Пн"
    assert await text.render_text({"week_day": 7}, None) == "Вс"


async def test_days_header_text():
    text = RuDaysHeaderText()
    assert (
        await text.render_text({"date": date(2026, 9, 17)}, None)
        == "🗓 Сентябрь 2026"
    )


def test_ru_calendar_views():
    """RuCalendar собирается и содержит все scope-виды."""
    calendar = RuCalendar(id="cal", config=CalendarConfig(firstweekday=0))
    assert set(calendar.views) == {
        CalendarScope.DAYS,
        CalendarScope.MONTHS,
        CalendarScope.YEARS,
    }
    assert calendar.config.firstweekday == 0


def test_ru_dicts_complete():
    """12 месяцев и 7 дней недели."""
    assert len(RU_MONTHS) == 12
    assert len(set(RU_MONTHS)) == 12
    assert sorted(RU_WEEKDAYS) == [1, 2, 3, 4, 5, 6, 7]
