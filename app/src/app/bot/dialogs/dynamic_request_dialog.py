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
- назад — по current_step - 1 (TIME → input_time_hour), с первого поля —
  к шагу телефона.

Значения из callback (час, минуты, индекс опции, дата) проверяются на
сервере: aiogram-dialog передаёт в on_click любое значение из callback_data,
ограничения виджетов (min/max_date, список опций) действуют только при отрисовке.
"""

from datetime import date

from aiogram import html
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
    current_field,
    current_step,
    field_getter,
    field_minute_step,
    field_options,
    get_bot_service,
    hours_getter,
    manager_start_answers,
    minutes_getter,
    normalize_answers,
    profile_getter,
    schema_of,
    select_options_getter,
    summary_getter,
)
from app.bot.services import BotService, BotServiceError
from app.bot.states import DynamicRequestSG
from app.bot.validators import normalize_phone
from app.bot.widgets.ru_calendar import RuCalendar, date_bounds
from app.domain.models import RequestFieldType
from app.domain.models.request_field_value import VALUE_TEXT_MAX_LENGTH

BACK_TEXT = Const("⬅️ Назад")

# Длина TEXT-поля по умолчанию (meta_data.max_length не задан)
DEFAULT_TEXT_MAX_LENGTH = 1000

# Окна диалога — простой текст (как до parse_mode=HTML по умолчанию у Bot):
# в summary выводится пользовательский ввод
WINDOW_PARSE_MODE = None

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


def _answers(manager: DialogManager) -> dict[int, str | None]:
    """Живой словарь ответов из start_data (запись по int-ключу).

    При перезагрузке из хранилища JSON превращает int-ключи в строки,
    поэтому читать ответы нужно через _get_answer (нормализация ключей).
    """
    return manager.start_data.setdefault("answers", {})


def _get_answer(manager: DialogManager, field_id: int) -> str | None:
    """Ответ поля с нормализацией ключей (JSON → str-ключи)."""
    return normalize_answers(_answers(manager)).get(field_id)


def _field_state(field: dict):
    """Состояние-окно по типу поля."""
    return _STATE_BY_TYPE[field["type"]]


def _meta(field: dict | None) -> dict:
    return (field or {}).get("meta_data") or {}


def _field_is_type(field: dict | None, field_type: RequestFieldType) -> bool:
    return field is not None and field["type"] == field_type.value


# ---------------------------------------------------------------------------
# Routing Engine
# ---------------------------------------------------------------------------


async def process_and_go_next(manager: DialogManager, value: str | None) -> None:
    """Записать ответ текущего поля, перейти к следующему (или summary)."""
    field = current_field(manager)
    if field is not None:
        _answers(manager)[field["id"]] = value
    step = current_step(manager) + 1
    manager.dialog_data["current_step"] = step
    schema = schema_of(manager)
    if step >= len(schema):
        await manager.switch_to(DynamicRequestSG.summary)
        return
    await manager.switch_to(_field_state(schema[step]))


async def go_back(manager: DialogManager) -> None:
    """Назад: к предыдущему полю схемы (TIME — к окну часов).

    С первого поля (и из summary при пустой схеме) — к шагу телефона.
    """
    schema = schema_of(manager)
    step = current_step(manager) - 1
    if not schema or step < 0:
        manager.dialog_data["current_step"] = 0
        await manager.switch_to(DynamicRequestSG.input_phone)
        return
    step = min(step, len(schema) - 1)
    manager.dialog_data["current_step"] = step
    await manager.switch_to(_field_state(schema[step]))


async def _skip_or_require(manager: DialogManager, callback: CallbackQuery) -> bool:
    """Пропуск поля: обязательное — отказ (alert), необязательное — None."""
    field = current_field(manager)
    if field is not None and field["is_required"]:
        await callback.answer(
            f"Поле «{field['label']}» обязательно.", show_alert=True
        )
        return False
    await process_and_go_next(manager, None)
    return True


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
    """Перехват нового номера: текст или контакт (сохраняется в профиле)."""
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
    # новый номер обновляет профиль посетителя (виден в админке)
    service: BotService = await get_bot_service(manager)
    try:
        await service.update_visitor_phone(message.from_user.id, phone)  # type: ignore[union-attr]
    except BotServiceError:
        pass  # посетитель не найден — заявка всё равно получит номер
    await _after_phone(manager)


async def _after_phone(manager: DialogManager) -> None:
    """Переход после телефона: первое поле схемы или сразу summary."""
    schema = schema_of(manager)
    manager.dialog_data["current_step"] = 0
    if not schema:
        await manager.switch_to(DynamicRequestSG.summary)
        return
    await manager.switch_to(_field_state(schema[0]))


# ---------------------------------------------------------------------------
# Поля TEXT / NUMBER (MessageInput)
# ---------------------------------------------------------------------------


def _text_max_length(field: dict | None) -> int:
    try:
        value = int(_meta(field).get("max_length", DEFAULT_TEXT_MAX_LENGTH))
    except (TypeError, ValueError):
        value = DEFAULT_TEXT_MAX_LENGTH
    return max(1, min(value, VALUE_TEXT_MAX_LENGTH))


def _meta_number(field: dict | None, key: str) -> float | None:
    """Число из meta_data (пустые/нечисловые значения игнорируются)."""
    value = _meta(field).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def parse_number(text: str) -> int | float:
    """Число из ввода: «5», «2.5», «2,5» (запятая — десятичный разделитель)."""
    normalized = text.replace(",", ".")
    if "." in normalized:
        return float(normalized)
    return int(normalized)


async def on_text_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Ввод TEXT-поля («-» → пропуск, если не обязательное)."""
    field = current_field(manager)
    text = (message.text or "").strip()
    if text == "-":
        if field and field["is_required"]:
            await message.answer(
                f"Поле «{html.quote(field['label'])}» обязательно. Введите значение:"
            )
            return
        await process_and_go_next(manager, None)
        return
    max_length = _text_max_length(field)
    if len(text) > max_length:
        await message.answer(f"Максимум {max_length} символов. Введите короче:")
        return
    await process_and_go_next(manager, text)


async def on_number_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Ввод NUMBER-поля («-» → пропуск, если не обязательное)."""
    field = current_field(manager)
    text = (message.text or "").strip()
    if text == "-":
        if field and field["is_required"]:
            await message.answer(
                f"Поле «{html.quote(field['label'])}» обязательно. Введите число:"
            )
            return
        await process_and_go_next(manager, None)
        return
    try:
        value = parse_number(text)
    except ValueError:
        await message.answer("Введите число (например 5 или 2.5):")
        return
    minimum = _meta_number(field, "min")
    maximum = _meta_number(field, "max")
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
    """Кнопка «Пропустить» (необязательное поле; проверяется на сервере)."""
    if await _skip_or_require(manager, callback):
        await callback.answer()


async def on_skip_input(
    message: Message, widget: MessageInput, manager: DialogManager,
) -> None:
    """Текст «-» в окнах выбора (дата/время/вариант) — пропуск необязательного поля."""
    field = current_field(manager)
    if (message.text or "").strip() != "-":
        await message.answer("Выберите значение кнопкой ниже.")
        return
    if field is not None and field["is_required"]:
        await message.answer(
            f"Поле «{html.quote(field['label'])}» обязательно. Выберите значение кнопкой:"
        )
        return
    await process_and_go_next(manager, None)


# ---------------------------------------------------------------------------
# Поля DATE (RuCalendar)
# ---------------------------------------------------------------------------


def _calendar_config() -> CalendarConfig:
    """Базовый конфиг календаря (неделя с понедельника).

    Границы дат (сегодня по МСК … +2 года) вычисляются на каждый рендер
    в RuCalendar._get_user_config.
    """
    return CalendarConfig(firstweekday=0)


async def on_date_selected(
    event, widget: ManagedCalendar, manager: DialogManager, selected_date: date,
) -> None:
    """Выбор даты в календаре → ISO-строка в answers (с проверкой границ)."""
    if not _field_is_type(current_field(manager), RequestFieldType.DATE):
        return
    min_date, max_date = date_bounds()
    if not min_date <= selected_date <= max_date:
        answer = getattr(event, "answer", None)
        if answer is not None:
            await answer("Эта дата недоступна", show_alert=True)
        return
    await process_and_go_next(manager, selected_date.isoformat())


# ---------------------------------------------------------------------------
# Поля TIME (час → минуты, temp_hour)
# ---------------------------------------------------------------------------


async def on_hour_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, hour: int,
) -> None:
    """Выбор часа → окно минут (current_step не меняется)."""
    if not 0 <= hour <= 23 or not _field_is_type(
        current_field(manager), RequestFieldType.TIME
    ):
        await callback.answer("Недопустимое значение", show_alert=True)
        return
    manager.dialog_data["temp_hour"] = hour
    await manager.switch_to(DynamicRequestSG.input_time_minute)


async def on_minute_selected(
    callback: CallbackQuery, select: Select, manager: DialogManager, minute: int,
) -> None:
    """Выбор минут: склеить «ЧЧ:ММ» → главный роутинг."""
    field = current_field(manager)
    hour = manager.dialog_data.get("temp_hour")
    step = field_minute_step(field)
    if (
        not _field_is_type(field, RequestFieldType.TIME)
        or not isinstance(hour, int)
        or not 0 <= hour <= 23
        or not 0 <= minute <= 59
        or minute % step != 0
    ):
        await callback.answer("Недопустимое значение", show_alert=True)
        return
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
    callback: CallbackQuery, select: Select, manager: DialogManager, index: int,
) -> None:
    """Выбор опции SELECT-поля (в callback — индекс опции, текст берётся из схемы)."""
    field = current_field(manager)
    options = field_options(field)
    if not _field_is_type(field, RequestFieldType.SELECT) or not 0 <= index < len(options):
        await callback.answer("Недопустимый вариант", show_alert=True)
        return
    await process_and_go_next(manager, options[index])


# ---------------------------------------------------------------------------
# Summary и финализация
# ---------------------------------------------------------------------------


async def on_submit(
    callback: CallbackQuery, button: Button, manager: DialogManager,
) -> None:
    """Кнопка «Отправить»: валидация обязательных полей → создание заявки."""
    schema = schema_of(manager)
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
        await callback.message.answer(f"Ошибка: {html.quote(str(exc))}")  # type: ignore[union-attr]
        await manager.done()
        return
    await manager.done()
    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Заявка #{req.id} создана. Менеджер свяжется с вами."
    )
    await callback.answer()


async def finalize_and_create(manager: DialogManager):
    """Финализация: создание заявки с динамическими полями через BotService."""
    service: BotService = await get_bot_service(manager)
    visitor = await service.get_active_visitor(manager.event.from_user.id)
    return await service.create_request(
        visitor=visitor,
        object_id=int(manager.start_data["object_id"]),
        phone=manager.dialog_data["phone"],
        values=manager_start_answers(manager),
    )


# ---------------------------------------------------------------------------
# Виджеты (переиспользуемые между окнами)
# ---------------------------------------------------------------------------

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
        # индекс опции (а не текст): callback_data ≤ 64 байт
        item_id_getter=lambda item: item[1],
        items="options",
        type_factory=int,
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

# «-» в окнах с кнопками выбора — пропуск необязательного поля
_SKIP_INPUT = MessageInput(on_skip_input, content_types="text")


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
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно TEXT-поля --------------------------------------------------------
    Window(
        Format("{field_label}\nОтправьте текст{skip_hint}:"),
        MessageInput(on_text_input, content_types="text"),
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=field_getter,
        state=DynamicRequestSG.input_text,
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно NUMBER-поля ------------------------------------------------------
    Window(
        Format("{field_label}\nОтправьте число{skip_hint}:"),
        MessageInput(on_number_input, content_types="text"),
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=field_getter,
        state=DynamicRequestSG.input_number,
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно DATE-поля --------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите дату:"),
        _CALENDAR_WIDGET,
        _SKIP_INPUT,
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=field_getter,
        state=DynamicRequestSG.input_date,
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно TIME: часы --------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите час:"),
        _HOURS_ROW,
        _SKIP_INPUT,
        _SKIP_BUTTON,
        _BACK_BUTTON,
        # CompositeGetter: данные поля (field_label) + список часов
        getter=[field_getter, hours_getter],
        state=DynamicRequestSG.input_time_hour,
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно TIME: минуты -------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите минуты:"),
        _MINUTES_ROW,
        _SKIP_INPUT,
        _SKIP_BUTTON,
        Button(
            Const("⬅️ К часам"),
            id="back_to_hours",
            on_click=on_back_to_hours,
        ),
        getter=[field_getter, minutes_getter],
        state=DynamicRequestSG.input_time_minute,
        parse_mode=WINDOW_PARSE_MODE,
    ),
    # -- Окно SELECT-поля ---------------------------------------------------------
    Window(
        Format("{field_label}\nВыберите вариант:"),
        _OPTIONS_ROW,
        _SKIP_INPUT,
        _SKIP_BUTTON,
        _BACK_BUTTON,
        getter=[field_getter, select_options_getter],
        state=DynamicRequestSG.input_select,
        parse_mode=WINDOW_PARSE_MODE,
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
        parse_mode=WINDOW_PARSE_MODE,
    ),
)
