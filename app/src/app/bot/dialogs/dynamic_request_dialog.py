"""Динамический конструктор заявки (aiogram-dialog).

Диалог строится по схеме полей категории объекта (start_data["schema"]):
телефон (фиксированный шаг) → поля схемы по типам → summary → создание.

Контекст:
- start_data["schema"]  — список полей (id, code, type, label, is_required, meta_data);
- start_data["answers"] — {field_id: value_str};
- dialog_data["current_step"] — индекс текущего поля в schema;
- dialog_data["temp_hour"] — выбранный час между окнами TIME.

Роутинг (Routing Engine):
- process_and_go_next(value) — записать ответ, шаг +1, переключение по
  типу следующего поля (TIME → input_time_hour), конец схемы → summary;
- on_hour_selected / on_minute_selected — двухшаговый ввод времени
  (temp_hour), минуты склеиваются в "ЧЧ:ММ" и передаются в process_and_go_next;
- назад — по current_step - 1 (TIME → input_time_hour).
"""

from datetime import date

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    CalendarConfig,
    ManagedCalendar,
    ScrollingGroup,
    Select,
)
from aiogram_dialog.widgets.text import Const, Format

from app.bot.dialogs.getters import (
    field_getter,
    get_bot_service,
    hours_getter_factory,
    manager_start_answers,
    minutes_getter,
    normalize_answers,
    profile_getter,
    select_options_getter,
    summary_getter,
)
from app.bot.dialogs.time_items import generate_hours
from app.bot.services import BotService, BotServiceError
from app.bot.states import DynamicRequestSG
from app.bot.validators import normalize_phone
from app.bot.widgets.ru_calendar import RuCalendar
from app.domain.models import RequestFieldType

BACK_TEXT = Const("⬅️ Назад")

# Состояние по типу поля (TIME → окно часов, минуты следуют без смены шага)
_STATE_BY_TYPE = {
    RequestFieldType.TEXT.value: DynamicRequestSG.input_text,
    RequestFieldType.NUMBER.value: DynamicRequestSG.input_number,
    RequestFieldType.DATE.value: DynamicRequestSG.input_date,
    RequestFieldType.TIME.value: DynamicRequestSG.input_time_hour,
    RequestFieldType.SELECT.value: DynamicRequestSG.input_select,
}


# ---------------------------------------------------------------------------
# Контекст диалога (schema / answers / current_step)
# ---------------------------------------------------------------------------


def _schema(manager: DialogManager) -> list[dict]:
    return manager.start_data.get("schema", [])


def _answers(manager: DialogManager) -> dict[int, str | None]:
    """Живой словарь ответов из start_data (запись по int-ключу).

    При перезагрузке из хранилища JSON превращает int-ключи в строки,
    поэтому читать ответы нужно через _get_answer (нормализация ключей).
    """
    return manager.start_data.setdefault("answers", {})


def _get_answer(manager: DialogManager, field_id: int) -> str | None:
    """Ответ поля с нормализацией ключей (JSON → str-ключи)."""
    return normalize_answers(_answers(manager)).get(field_id)


def _current_step(manager: DialogManager) -> int:
    return int(manager.dialog_data.get("current_step", 0))


def _current_field(manager: DialogManager) -> dict | None:
    schema = _schema(manager)
    step = _current_step(manager)
    if 0 <= step < len(schema):
        return schema[step]
    return None


def _field_state(field: dict):
    """Состояние-окно по типу поля."""
    return _STATE_BY_TYPE[field["type"]]


# ---------------------------------------------------------------------------
# Routing Engine
# ---------------------------------------------------------------------------


async def process_and_go_next(manager: DialogManager, value: str | None) -> None:
    """Записать ответ текущего поля, перейти к следующему (или summary)."""
    field = _current_field(manager)
    if field is not None:
        _answers(manager)[field["id"]] = value
    step = _current_step(manager) + 1
    manager.dialog_data["current_step"] = step
    schema = _schema(manager)
    if step >= len(schema):
        await manager.switch_to(DynamicRequestSG.summary)
        return
    await manager.switch_to(_field_state(schema[step]))


async def go_back(manager: DialogManager) -> None:
    """Назад: к предыдущему полю схемы (TIME — к окну часов)."""
    step = max(0, _current_step(manager) - 1)
    manager.dialog_data["current_step"] = step
    schema = _schema(manager)
    if not schema:
        await manager.switch_to(DynamicRequestSG.input_phone)
        return
    await manager.switch_to(_field_state(schema[step]))


# ---------------------------------------------------------------------------
# Окно 1: телефон (фиксированный шаг)
# ---------------------------------------------------------------------------


async def on_use_profile_phone(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Кнопка «Использовать номер из профиля»."""
    service: BotService = await get_bot_service(manager)
    phone = await service.get_profile_phone(callback.from_user.id)
    if phone:
        manager.dialog_data["phone"] = phone
        await _after_phone(manager)
        await callback.answer()
    else:
        await callback.answer(
            "Номер в профиле не найден. Отправьте номер сообщением.",
            show_alert=True,
        )


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
    await _after_phone(manager)


async def _after_phone(manager: DialogManager) -> None:
    """Переход после телефона: первое поле схемы или сразу summary."""
    schema = _schema(manager)
    manager.dialog_data["current_step"] = 0
    if not schema:
        await manager.switch_to(DynamicRequestSG.summary)
        return
    await manager.switch_to(_field_state(schema[0]))


# ---------------------------------------------------------------------------
# Поля TEXT / NUMBER (MessageInput)
# ---------------------------------------------------------------------------


async def on_text_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Ввод TEXT-поля («-» → пропуск, если не обязательное)."""
    field = _current_field(manager)
    text = (message.text or "").strip()
    if text == "-":
        if field and field["is_required"]:
            await message.answer(
                f"Поле «{field['label']}» обязательно. Введите значение:"
            )
            return
        await process_and_go_next(manager, None)
        return
    max_length = int((field or {}).get("meta_data", {}).get("max_length", 1000))
    if len(text) > max_length:
        await message.answer(f"Максимум {max_length} символов. Введите короче:")
        return
    await process_and_go_next(manager, text)


async def on_number_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Ввод NUMBER-поля («-» → пропуск, если не обязательное)."""
    field = _current_field(manager)
    text = (message.text or "").strip()
    if text == "-":
        if field and field["is_required"]:
            await message.answer(
                f"Поле «{field['label']}» обязательно. Введите число:"
            )
            return
        await process_and_go_next(manager, None)
        return
    try:
        value = float(text) if "." in text or "," in text else int(text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число (например 5 или 2.5):")
        return
    meta = (field or {}).get("meta_data", {})
    minimum = meta.get("min")
    maximum = meta.get("max")
    if minimum is not None and value < minimum:
        await message.answer(f"Минимум: {minimum}. Введите число:")
        return
    if maximum is not None and value > maximum:
        await message.answer(f"Максимум: {maximum}. Введите число:")
        return
    # унифицированное текстовое хранение
    await process_and_go_next(manager, str(value))


async def on_skip_field(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Кнопка «Пропустить» (необязательное поле)."""
    await process_and_go_next(manager, None)
    await callback.answer()


# ---------------------------------------------------------------------------
# Поля DATE (RuCalendar)
# ---------------------------------------------------------------------------


def _calendar_config() -> CalendarConfig:
    """Конфиг календаря: от сегодня до +2 лет (вычисляется на каждый рендер)."""
    today = date.today()
    return CalendarConfig(
        firstweekday=0,
        min_date=today,
        max_date=today.replace(year=today.year + 2),
    )


async def _calendar_getter(**kwargs) -> dict:
    """Геттер окна с датами: свежий CalendarConfig на каждый рендер."""
    return {"calendar_config": _calendar_config()}


async def on_date_selected(
    event, widget: ManagedCalendar, manager: DialogManager, selected_date: date,
) -> None:
    """Выбор даты в календаре → ISO-строка в answers."""
    await process_and_go_next(manager, selected_date.isoformat())


# ---------------------------------------------------------------------------
# Поля TIME (час → минуты, temp_hour)
# ---------------------------------------------------------------------------


async def on_hour_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, hour: int,
) -> None:
    """Выбор часа → окно минут (current_step не меняется)."""
    manager.dialog_data["temp_hour"] = hour
    await manager.switch_to(DynamicRequestSG.input_time_minute)


async def on_minute_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, minute: int,
) -> None:
    """Выбор минут: склеить «ЧЧ:ММ» → главный роутинг."""
    hour = int(manager.dialog_data.get("temp_hour", 0))
    await process_and_go_next(manager, f"{hour:02d}:{minute:02d}")


async def on_back_to_hours(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Назад от минут к часам (то же поле, шаг не меняется)."""
    await manager.switch_to(DynamicRequestSG.input_time_hour)
    await callback.answer()


# ---------------------------------------------------------------------------
# Поля SELECT (опции из meta_data)
# ---------------------------------------------------------------------------


async def on_option_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, option: str,
) -> None:
    """Выбор опции SELECT-поля."""
    await process_and_go_next(manager, option)


# ---------------------------------------------------------------------------
# Summary и финализация
# ---------------------------------------------------------------------------


async def on_submit(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Кнопка «Отправить»: валидация обязательных полей → создание заявки."""
    schema = _schema(manager)
    missing = [
        f for f in schema
        if f["is_required"] and not _get_answer(manager, f["id"])
    ]
    if missing:
        labels = ", ".join(f['label'] for f in missing)
        await callback.answer(f"Не заполнено: {labels}", show_alert=True)
        return
    try:
        req = await finalize_and_create(manager)
    except (BotServiceError, KeyError) as exc:
        await callback.message.answer(f"Ошибка: {exc}")  # type: ignore[union-attr]
        await manager.done()
        return
    await manager.done()
    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Заявка #{req.id} создана. Менеджер свяжется с вами."
    )
    await callback.answer()


async def finalize_and_create(manager: DialogManager):
    """Финализация: создание заявки с динамическими полями через BotService."""
    container = manager.middleware_data["dishka_container"]
    service: BotService = await container.get(BotService)
    visitor = await service.get_visitor(manager.event.from_user.id)
    if visitor is None:
        raise BotServiceError("Сначала завершите регистрацию (/start).")
    if visitor.is_blocked:
        raise BotServiceError("Вы заблокированы.")
    return await service.create_request(
        visitor=visitor,
        object_id=int(manager.start_data["object_id"]),
        phone=manager.dialog_data["phone"],
        values=manager_start_answers(manager),
    )


# ---------------------------------------------------------------------------
# Виджеты (переиспользуемые между окнами)
# ---------------------------------------------------------------------------

HOURS = generate_hours()

_CALENDAR_WIDGET = RuCalendar(
    id="cal_field_date",
    on_click=on_date_selected,
    config=_calendar_config(),
)

_HOURS_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_time_hour",
        item_id_getter=lambda item: str(item[1]),
        items="hours",
        type_factory=int,
        on_click=on_hour_selected,
    ),
    id="sg_time_hour",
    width=6,
    height=4,
)

_MINUTES_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_time_minute",
        item_id_getter=lambda item: str(item[1]),
        items="minutes",
        type_factory=int,
        on_click=on_minute_selected,
    ),
    id="sg_time_minute",
    width=6,
    height=2,
)

_OPTIONS_ROW = ScrollingGroup(
    Select(
        Format("{item[0]}"),
        id="sel_option",
        item_id_getter=lambda item: item[1],
        items="options",
        on_click=on_option_selected,
    ),
    id="sg_options",
    width=1,
    height=8,
)

_SKIP_BUTTON = Button(
    Const("⏭ Пропустить"),
    id="btn_skip",
    on_click=on_skip_field,
    when="not_required",
)


async def _on_back_click(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Общий обработчик кнопки «Назад»."""
    await go_back(manager)
    await callback.answer()


_BACK_BUTTON = Button(BACK_TEXT, id="btn_back", on_click=_on_back_click)


# ---------------------------------------------------------------------------
# Диалог
# ---------------------------------------------------------------------------

dialog = Dialog(
    # -- Окно 1: телефон -----------------------------------------------------
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
        state=DynamicRequestSG.input_phone,
    ),
    # -- Окно TEXT-поля --------------------------------------------------------
    Window(
        Format("{field_label}\nОтправьте текст{skip_hint}:"),
        MessageInput(on_text_input, content_types="text"),
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=field_getter,
        state=DynamicRequestSG.input_text,
    ),
    # -- Окно NUMBER-поля ------------------------------------------------------
    Window(
        Format("{field_label}\nОтправьте число{skip_hint}:"),
        MessageInput(on_number_input, content_types="text"),
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=field_getter,
        state=DynamicRequestSG.input_number,
    ),
    # -- Окно DATE-поля --------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите дату:"),
        _CALENDAR_WIDGET,
        _SKIP_BUTTON,
        _BACK_BUTTON,
        # aiogram-dialog вызывает геттеры как getter(**middleware_data),
        # где менеджер лежит под ключом "dialog_manager"
        getter=lambda dialog_manager, **kw: _combined_getter(dialog_manager, kw),
        state=DynamicRequestSG.input_date,
    ),
    # -- Окно TIME: часы --------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите час:"),
        _HOURS_ROW,
        _BACK_BUTTON,
        # CompositeGetter: данные поля (field_label) + список часов/минут
        getter=[field_getter, hours_getter_factory()],
        state=DynamicRequestSG.input_time_hour,
    ),
    # -- Окно TIME: минуты -------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите минуты:"),
        _MINUTES_ROW,
        Button(
            Const("⬅️ К часам"),
            id="back_to_hours",
            on_click=on_back_to_hours,
        ),
        getter=[field_getter, minutes_getter],
        state=DynamicRequestSG.input_time_minute,
    ),
    # -- Окно SELECT-поля ---------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите вариант:"),
        _OPTIONS_ROW,
        _BACK_BUTTON,
        getter=[field_getter, select_options_getter],
        state=DynamicRequestSG.input_select,
    ),
    # -- Summary -------------------------------------------------------------------
    Window(
        Format(
            "Проверьте заявку:\n\n"
            "📱 Телефон: {phone}\n\n{summary_lines}\n\n"
            "Отправить заявку?"
        ),
        Button(Const("✅ Отправить"), id="btn_submit", on_click=on_submit),
        _BACK_BUTTON,
        getter=summary_getter,
        state=DynamicRequestSG.summary,
    ),
)


async def _combined_getter(manager: DialogManager, kwargs: dict) -> dict:
    """Геттер окна DATE: данные поля + свежий CalendarConfig."""
    result = await field_getter(manager, **kwargs)
    result.update(await _calendar_getter())
    return result