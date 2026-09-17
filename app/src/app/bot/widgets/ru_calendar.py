"""Русифицированный календарь для aiogram-dialog.

Штатный Calendar не переводит названия месяцев и дней недели
(см. документацию aiogram-dialog), поэтому RuCalendar переопределяет
_init_views и передаёт собственные Text-виджеты с русскими текстами:

- заголовок дней: «🗓 Сентябрь 2026»;
- дни недели: Пн Вт Ср Чт Пт Сб Вс;
- кнопки месяцев: Январь … Декабрь;
- навигация: ◀️ / ▶️, сегодня подсвечивается как «[ 17 ]».

Неделя начинается с понедельника (firstweekday=0, см. CalendarConfig).
"""

from datetime import date

from aiogram_dialog.api.internal import TextWidget
from aiogram_dialog.widgets.common import WhenCondition
from aiogram_dialog.widgets.kbd import Calendar, CalendarScope
from aiogram_dialog.widgets.kbd.calendar_kbd import (
    CalendarDaysView,
    CalendarMonthView,
    CalendarScopeView,
    CalendarYearsView,
)
from aiogram_dialog.widgets.text import Const, Format, Text

RU_MONTHS = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

# week_day в заголовке дней: 1 = понедельник … 7 = воскресенье
RU_WEEKDAYS = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}


class RuMonthText(Text):
    """Название месяца по ключу month (или из date)."""

    async def _render_text(self, data: dict, manager) -> str:  # noqa: ANN001
        month = data.get("month") or data["date"].month
        return RU_MONTHS[int(month) - 1]


class RuWeekdayText(Text):
    """Короткое название дня недели (Пн … Вс)."""

    async def _render_text(self, data: dict, manager) -> str:  # noqa: ANN001
        return RU_WEEKDAYS[int(data["week_day"])]


class RuDaysHeaderText(Text):
    """Заголовок окна дней: «🗓 Сентябрь 2026»."""

    async def _render_text(self, data: dict, manager) -> str:  # noqa: ANN001
        d: date = data["date"]
        return f"🗓 {RU_MONTHS[d.month - 1]} {d.year}"


class RuCalendar(Calendar):
    """Календарь с русскими названиями месяцев и дней недели."""

    def _init_views(self) -> dict[CalendarScope, CalendarScopeView]:
        days_view = CalendarDaysView(
            self._item_callback_data,
            today_text=Format("[ {date:%d} ]"),
            weekday_text=RuWeekdayText(),
            header_text=RuDaysHeaderText(),
            zoom_out_text=Const("🗓 Год"),
            next_month_text=Const("▶️"),
            prev_month_text=Const("◀️"),
        )
        months_view = CalendarMonthView(
            self._item_callback_data,
            month_text=RuMonthText(),
            this_month_text=_Bracket(RuMonthText()),
            header_text=Format("🗓 {date:%Y}"),
            zoom_out_text=Const("🗓 Годы"),
            next_year_text=Format("{date:%Y} >>"),
            prev_year_text=Format("<< {date:%Y}"),
        )
        years_view = CalendarYearsView(self._item_callback_data)
        return {
            CalendarScope.DAYS: days_view,
            CalendarScope.MONTHS: months_view,
            CalendarScope.YEARS: years_view,
        }


class _Bracket(Text):
    """Обёртка: выводит внутренний текст в квадратных скобках."""

    def __init__(self, inner: TextWidget, when: WhenCondition = None) -> None:
        super().__init__(when=when)
        self.inner = inner

    async def _render_text(self, data: dict, manager) -> str:  # noqa: ANN001
        return f"[ {await self.inner.render_text(data, manager)} ]"
