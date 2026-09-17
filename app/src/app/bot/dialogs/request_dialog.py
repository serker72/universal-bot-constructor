"""Диалог создания заявки (aiogram-dialog).

Окна:
1. input_phone — телефон (из профиля или новый: текст/контакт);
2. start_date — начальная дата (RuCalendar);
3. start_hour / 4. start_min — время начала (Select часы/минуты);
5. end_date — дата окончания (RuCalendar);
6. end_hour / 7. end_min — время окончания (Select часы/минуты);
8. input_comment — комментарий («-» → None).

Роутинг динамический, зависит от флагов start_data:
- is_use_time_in_request — показывать окна времени;
- is_use_end_date_in_request — показывать окна даты/времени окончания.
"""

from datetime import date, datetime, time

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    CalendarConfig,
    ManagedCalendar,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format

from app.bot.dialogs.getters import hours_getter_factory, profile_getter
from app.bot.dialogs.time_items import generate_hours, generate_minutes
from app.bot.services import BotService, BotServiceError
from app.bot.states import RequestStates
from app.bot.validators import normalize_phone
from app.bot.widgets.ru_calendar import RuCalendar

FLAG_USE_TIME = "is_use_time_in_request"
FLAG_USE_END_DATE = "is_use_end_date_in_request"

BACK_TEXT = Const("⬅️ Назад")


def _use_time(manager: DialogManager) -> bool:
    return bool(manager.start_data.get(FLAG_USE_TIME))


def _use_end_date(manager: DialogManager) -> bool:
    return bool(manager.start_data.get(FLAG_USE_END_DATE))


# ---------------------------------------------------------------------------
# Окно 1: телефон
# ---------------------------------------------------------------------------


async def on_use_profile_phone(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Кнопка «Использовать номер из профиля»."""
    phone = manager.dialog_data.get("profile_phone")
    if phone:
        manager.dialog_data["phone"] = phone
        await manager.switch_to(RequestStates.start_date)
    await callback.answer()


async def on_phone_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Перехват нового номера: текст или контакт."""
    raw = None
    if message.contact is not None:
        raw = message.contact.phone_number
    elif message.text:
        raw = message.text
    phone = normalize_phone(raw) if raw else None
    if phone is None:
        await message.answer(
            "Некорректный номер. Введите телефон в формате +79001234567:"
        )
        return
    manager.dialog_data["phone"] = phone
    await manager.switch_to(RequestStates.start_date)


# ---------------------------------------------------------------------------
# Окна 2/5: даты (RuCalendar)
# ---------------------------------------------------------------------------


async def _after_start_date(manager: DialogManager) -> None:
    """Переход после выбора начальной даты (по флагам)."""
    if _use_time(manager):
        await manager.switch_to(RequestStates.start_hour)
    elif _use_end_date(manager):
        await manager.switch_to(RequestStates.end_date)
    else:
        await manager.switch_to(RequestStates.input_comment)


async def on_start_date_selected(
    event, widget: ManagedCalendar, manager: DialogManager, selected_date: date,
) -> None:
    """Выбор начальной даты в календаре."""
    manager.dialog_data["start_date"] = selected_date.isoformat()
    await _after_start_date(manager)


async def on_end_date_selected(
    event, widget: ManagedCalendar, manager: DialogManager, selected_date: date,
) -> None:
    """Выбор даты окончания в календаре."""
    manager.dialog_data["end_date"] = selected_date.isoformat()
    if _use_time(manager):
        await manager.switch_to(RequestStates.end_hour)
    else:
        await manager.switch_to(RequestStates.input_comment)


# ---------------------------------------------------------------------------
# Окна 3/4/6/7: время (Select)
# ---------------------------------------------------------------------------


async def on_start_hour_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, hour: int,
) -> None:
    """Выбор часа начала → минуты начала."""
    manager.dialog_data["start_hour"] = hour
    await manager.switch_to(RequestStates.start_min)


async def on_start_min_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, minute: int,
) -> None:
    """Выбор минут начала → дата окончания или комментарий (по флагу)."""
    manager.dialog_data["start_min"] = minute
    if _use_end_date(manager):
        await manager.switch_to(RequestStates.end_date)
    else:
        await manager.switch_to(RequestStates.input_comment)


async def on_end_hour_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, hour: int,
) -> None:
    """Выбор часа окончания → минуты окончания."""
    manager.dialog_data["end_hour"] = hour
    await manager.switch_to(RequestStates.end_min)


async def on_end_min_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, minute: int,
) -> None:
    """Выбор минут окончания → комментарий."""
    manager.dialog_data["end_min"] = minute
    await manager.switch_to(RequestStates.input_comment)


# ---------------------------------------------------------------------------
# Обратная навигация (Backward Routing)
# ---------------------------------------------------------------------------


async def on_back_from_end_date(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Назад от даты окончания: время начала или начальная дата."""
    if _use_time(manager):
        await manager.switch_to(RequestStates.start_min)
    else:
        await manager.switch_to(RequestStates.start_date)
    await callback.answer()


async def on_back_from_comment(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Назад от комментария: последний включённый шаг по флагам."""
    if _use_end_date(manager) and _use_time(manager):
        await manager.switch_to(RequestStates.end_min)
    elif _use_end_date(manager):
        await manager.switch_to(RequestStates.end_date)
    elif _use_time(manager):
        await manager.switch_to(RequestStates.start_min)
    else:
        await manager.switch_to(RequestStates.start_date)
    await callback.answer()


# ---------------------------------------------------------------------------
# Окно 8: комментарий и финализация
# ---------------------------------------------------------------------------


def _build_datetimes(data: dict) -> tuple[datetime | None, datetime | None]:
    """Собрать полные datetime (если заданы дата и время) из dialog_data."""
    start = end = None
    if data.get("start_date"):
        start = datetime.combine(
            date.fromisoformat(data["start_date"]),
            time(data.get("start_hour", 0), data.get("start_min", 0)),
        )
    if data.get("end_date"):
        end = datetime.combine(
            date.fromisoformat(data["end_date"]),
            time(data.get("end_hour", 0), data.get("end_min", 0)),
        )
    return start, end


def validate_request_data(data: dict) -> str | None:
    """Валидация бизнес-правил. Возвращает текст ошибки или None."""
    start_date = (
        date.fromisoformat(data["start_date"]) if data.get("start_date") else None
    )
    end_date = date.fromisoformat(data["end_date"]) if data.get("end_date") else None
    if start_date and end_date and end_date < start_date:
        return "Дата окончания не может быть раньше даты начала."
    if start_date and end_date and start_date == end_date:
        start, end = _build_datetimes(data)
        if start is not None and end is not None and end < start:
            return "Время окончания не может быть раньше времени начала."
    return None


def collect_request_data(manager: DialogManager) -> dict:
    """Агрегация данных заявки из dialog_data."""
    data = manager.dialog_data
    use_time = _use_time(manager)
    use_end_date = _use_end_date(manager)
    return {
        "phone": data["phone"],
        "comment": data.get("comment"),
        "start_date": (
            date.fromisoformat(data["start_date"])
            if data.get("start_date") else None
        ),
        "start_time": (
            time(data.get("start_hour", 0), data.get("start_min", 0))
            if use_time and data.get("start_date") else None
        ),
        "end_date": (
            date.fromisoformat(data["end_date"])
            if use_end_date and data.get("end_date") else None
        ),
        "end_time": (
            time(data.get("end_hour", 0), data.get("end_min", 0))
            if use_time and use_end_date and data.get("end_date") else None
        ),
    }


async def on_comment_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Комментарий («-» → None) → валидация → создание заявки → done."""
    comment = (message.text or "").strip()
    comment = None if comment in ("-", "") else comment
    manager.dialog_data["comment"] = comment

    error = validate_request_data(manager.dialog_data)
    if error is not None:
        await message.answer(f"⚠️ {error} Исправьте даты.")
        # возврат на шаг выбора даты, где ошибка исправима
        if _use_end_date(manager):
            await manager.switch_to(RequestStates.end_date)
        else:
            await manager.switch_to(RequestStates.start_date)
        return

    try:
        req = await finalize_and_create(manager)
    except (BotServiceError, KeyError) as exc:
        await message.answer(f"Ошибка: {exc}", reply_markup=None)
        await manager.done()
        return

    await manager.done()
    await message.answer(
        f"✅ Заявка #{req.id} создана. Менеджер свяжется с вами."
    )


async def finalize_and_create(manager: DialogManager):
    """Финализация: агрегация данных и создание заявки через BotService."""
    container = manager.middleware_data["dishka_container"]
    service: BotService = await container.get(BotService)
    visitor = await service.get_visitor(manager.event.from_user.id)
    if visitor is None:
        raise BotServiceError("Сначала завершите регистрацию (/start).")
    if visitor.is_blocked:
        raise BotServiceError("Вы заблокированы.")
    payload = collect_request_data(manager)
    return await service.create_request(
        visitor=visitor,
        object_id=int(manager.start_data["object_id"]),
        **payload,
    )


# ---------------------------------------------------------------------------
# Окна диалога
# ---------------------------------------------------------------------------

HOURS = generate_hours()
MINUTES = generate_minutes()

# Календарь заявки: неделя с понедельника, даты не в прошлом и не далее +2 лет
_CALENDAR_CONFIG = CalendarConfig(
    firstweekday=0,
    min_date=date.today(),
    max_date=date.today().replace(year=date.today().year + 2),
)

_START_CALENDAR_WIDGET = RuCalendar(
    id="cal_start_date",
    on_click=on_start_date_selected,
    config=_CALENDAR_CONFIG,
)

_END_CALENDAR_WIDGET = RuCalendar(
    id="cal_end_date",
    on_click=on_end_date_selected,
    config=_CALENDAR_CONFIG,
)

_HOURS_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_start_hour",
        item_id_getter=lambda item: str(item[1]),
        items="hours",
        type_factory=int,
        on_click=on_start_hour_selected,
    ),
    id="sg_start_hour",
    width=6,
    height=4,
)

_START_MIN_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_start_min",
        item_id_getter=lambda item: str(item[1]),
        items="minutes",
        type_factory=int,
        on_click=on_start_min_selected,
    ),
    id="sg_start_min",
    width=6,
    height=2,
)

_END_HOURS_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_end_hour",
        item_id_getter=lambda item: str(item[1]),
        items="hours",
        type_factory=int,
        on_click=on_end_hour_selected,
    ),
    id="sg_end_hour",
    width=6,
    height=4,
)

_END_MIN_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_end_min",
        item_id_getter=lambda item: str(item[1]),
        items="minutes",
        type_factory=int,
        on_click=on_end_min_selected,
    ),
    id="sg_end_min",
    width=6,
    height=2,
)

_START_CALENDAR = RuCalendarRef = None  # placeholder, заменяется ниже

dialog = Dialog(
    # -- Окно 1: телефон ----------------------------------------------------
    Window(
        Format("{phone_text}"),
        Button(
            Const("📱 Использовать номер из профиля"),
            id="use_profile_phone",
            on_click=on_use_profile_phone,
            when="profile_phone",
        ),
        MessageInput(on_phone_input, content_types=("text", "contact")),
        getter=profile_getter,
        state=RequestStates.input_phone,
    ),
    # -- Окно 2: начальная дата ---------------------------------------------
    Window(
        Const("📅 Выберите дату начала:"),
        _START_CALENDAR_WIDGET,
        SwitchTo(BACK_TEXT, id="back_phone", state=RequestStates.input_phone),
        state=RequestStates.start_date,
    ),
    # -- Окно 3: час начала ---------------------------------------------------
    Window(
        Const("🕐 Выберите час начала:"),
        _HOURS_ROW,
        SwitchTo(BACK_TEXT, id="back_sdate", state=RequestStates.start_date),
        getter=hours_getter_factory(),
        state=RequestStates.start_hour,
    ),
    # -- Окно 4: минуты начала ------------------------------------------------
    Window(
        Const("🕐 Выберите минуты начала:"),
        _START_MIN_ROW,
        SwitchTo(BACK_TEXT, id="back_shour", state=RequestStates.start_hour),
        getter=hours_getter_factory(),
        state=RequestStates.start_min,
    ),
    # -- Окно 5: дата окончания ------------------------------------------------
    Window(
        Const("📅 Выберите дату окончания:"),
        _END_CALENDAR_WIDGET,
        Button(
            BACK_TEXT,
            id="back_end_date",
            on_click=on_back_from_end_date,
        ),
        state=RequestStates.end_date,
    ),
    # -- Окно 6: час окончания --------------------------------------------------
    Window(
        Const("🕐 Выберите час окончания:"),
        _END_HOURS_ROW,
        SwitchTo(BACK_TEXT, id="back_edate", state=RequestStates.end_date),
        getter=hours_getter_factory(),
        state=RequestStates.end_hour,
    ),
    # -- Окно 7: минуты окончания -------------------------------------------------
    Window(
        Const("🕐 Выберите минуты окончания:"),
        _END_MIN_ROW,
        SwitchTo(BACK_TEXT, id="back_ehour", state=RequestStates.end_hour),
        getter=hours_getter_factory(),
        state=RequestStates.end_min,
    ),
    # -- Окно 8: комментарий ---------------------------------------------------
    Window(
        Const(
            "💬 Добавьте комментарий к заявке\n"
            "(или отправьте «-» чтобы пропустить):"
        ),
        MessageInput(on_comment_input, content_types="text"),
        Button(
            BACK_TEXT,
            id="back_comment",
            on_click=on_back_from_comment,
        ),
        state=RequestStates.input_comment,
    ),
)
