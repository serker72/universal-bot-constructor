"""Геттеры окон диалогов бота.

Геттер профиля читает сохранённый телефон посетителя (visitors.phone)
через BotService из dishka-контейнера (REQUEST-scope, dishka_container
в middleware_data).

Геттеры динамического диалога заявки работают с контекстом:
- start_data["schema"] — список полей категории (dict);
- start_data["answers"] — {field_id: value_str};
- dialog_data["current_step"] — индекс текущего поля в schema;
- dialog_data["temp_hour"] — выбранный час между окнами TIME.
"""

from aiogram_dialog import DialogManager

from app.bot.dialogs.time_items import MINUTES_STEP, generate_hours, generate_minutes
from app.bot.services import BotService


async def get_bot_service(manager: DialogManager) -> BotService:
    """BotService из dishka-контейнера текущего обновления."""
    container = manager.middleware_data["dishka_container"]
    return await container.get(BotService)


async def profile_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Текущий телефон из профиля посетителя (или None) + текст окна."""
    service = await get_bot_service(dialog_manager)
    profile_phone = await service.get_profile_phone(
        dialog_manager.event.from_user.id
    )
    if profile_phone:
        phone_text = (
            f"Ваш номер: {profile_phone}\n"
            "Отправьте новый номер или выберите его ниже."
        )
    else:
        phone_text = "Отправьте ваш номер телефона (например, +79001234567):"
    return {"profile_phone": profile_phone, "phone_text": phone_text}


# -- контекст динамического конструктора заявки (общий для диалога) ---------


def schema_of(manager: DialogManager) -> list[dict]:
    """Массив полей схемы заявки из start_data."""
    return manager.start_data.get("schema", [])


def current_step(manager: DialogManager) -> int:
    """Индекс текущего поля схемы."""
    return int(manager.dialog_data.get("current_step", 0))


def current_field(manager: DialogManager) -> dict | None:
    """Поле схемы по current_step (или None — схема закончилась)."""
    schema = schema_of(manager)
    step = current_step(manager)
    if 0 <= step < len(schema):
        return schema[step]
    return None


def field_options(field: dict | None) -> list[str]:
    """Опции SELECT-поля из meta_data."""
    if field is None:
        return []
    return [str(o) for o in (field.get("meta_data") or {}).get("options", [])]


def field_minute_step(field: dict | None) -> int:
    """Шаг минут TIME-поля из meta_data (по умолчанию MINUTES_STEP)."""
    if field is None:
        return MINUTES_STEP
    try:
        return int((field.get("meta_data") or {}).get("minute_step", MINUTES_STEP))
    except (TypeError, ValueError):
        return MINUTES_STEP


# -- геттеры окон --------------------------------------------------------------


async def field_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Данные текущего поля: подпись, признак необязательности, подсказка."""
    field = current_field(dialog_manager)
    if field is None:
        return {"field_label": "", "not_required": True, "skip_hint": ""}
    required = bool(field["is_required"])
    label = field["label"] + (" (обязательно)" if required else "")
    return {
        "field_label": label,
        "not_required": not required,
        # подсказка про «-» только для необязательных полей
        "skip_hint": "" if required else " (или «-» чтобы пропустить)",
    }


async def hours_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Часы 00–23 для окна выбора часа."""
    return {"hours": generate_hours()}


async def minutes_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Минуты с шагом из meta_data текущего TIME-поля."""
    step = field_minute_step(current_field(dialog_manager))
    return {"minutes": generate_minutes(step)}


async def select_options_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Опции SELECT-поля: (текст, индекс).

    В callback_data передаётся индекс опции, а не её текст: лимит
    callback_data — 64 байта, кириллический текст опции его превышает.
    """
    options = field_options(current_field(dialog_manager))
    return {"options": [(text, str(index)) for index, text in enumerate(options)]}


async def summary_getter(dialog_manager: DialogManager, **kwargs) -> dict:
    """Сводка: список «label: value» по всем полям схемы + телефон."""
    schema = schema_of(dialog_manager)
    answers: dict[int, str | None] = manager_start_answers(dialog_manager)
    lines = []
    for f in schema:
        value = answers.get(f["id"])
        lines.append(f"• {f['label']}: {value if value else '—'}")
    phone = dialog_manager.dialog_data.get("phone", "")
    return {
        "summary_lines": "\n".join(lines) if lines else "Дополнительные поля не заданы.",
        "phone": phone,
    }


def normalize_answers(raw: dict) -> dict[int, str | None]:
    """Ключи answers → int.

    start_data сериализуется в JSON, где int-ключи dict становятся
    строками — после перезагрузки из хранилища ответы приходят как
    {"3": "5"}, поэтому ключи приводятся к int на каждом чтении.
    """
    if not any(isinstance(key, str) for key in raw):
        return raw
    return {int(key): value for key, value in raw.items()}


def manager_start_answers(manager: DialogManager) -> dict[int, str | None]:
    """Словарь ответов {field_id: value} из start_data."""
    return normalize_answers(manager.start_data.get("answers", {}))
