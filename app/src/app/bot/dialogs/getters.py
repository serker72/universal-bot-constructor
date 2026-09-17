"""Геттеры окон диалога создания заявки.

Геттер профиля читает сохранённый телефон посетителя (visitors.phone)
через BotService из dishka-контейнера (REQUEST-scope, dishka_container
в middleware_data).
"""

from aiogram_dialog import DialogManager

from app.bot.dialogs.time_items import generate_hours, generate_minutes
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


def hours_getter_factory(step: int = 5):
    """Асинхронный геттер списка часов/минут для окон выбора времени.

    Геттеры aiogram-dialog обязаны быть корутинами (фреймворк делает await).
    """

    async def time_items_getter(**kwargs) -> dict:
        return {
            "hours": generate_hours(),
            "minutes": generate_minutes(step),
        }

    return time_items_getter
