"""Консьюмеры RabbitMQ: уведомления через Telegram.

Подписки (routing keys издателя, см. app.services.events):
- notifications.registration      — новая регистрация → админы;
- notifications.request.created   — новая заявка → менеджеры объекта;
- notifications.request.cancelled — отмена заявки → менеджеры объекта.

ВАЖНО: подписчики регистрируются ДО первого broker.start() — подписчики,
добавленные после старта брокера, не создают очередей (faststream 0.7).
Имена очередей — в .env (CONSUMER_QUEUE_*).

Если у пользователя не указан telegram_id — уведомление пропускается.
"""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dishka import AsyncContainer
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.config.settings import Settings
from app.domain.models import UserRole
from app.log import get_logger
from app.repository.user import UserRepository
from app.services.events import (
    RequestCancelledEvent,
    RequestCreatedEvent,
    RequestStatusChangedEvent,
    VisitorRegisteredEvent,
)

# Тексты статусов заявки для посетителя
STATUS_TEXT = {
    "approved": "✅ Ваша заявка #{request_id} подтверждена менеджером.",
    "rejected": "❌ Ваша заявка #{request_id} отклонена менеджером.",
    "completed": "🏁 Заявка #{request_id} выполнена. Спасибо за обращение!",
}

log = get_logger(__name__)


def register_notification_consumers(
    broker: RabbitBroker, container: AsyncContainer, settings: Settings
) -> None:
    """Зарегистрировать подписчиков уведомлений на брокере (до broker.start())."""
    queues = (
        RabbitQueue(
            name=settings.consumer.queue_registration,
            durable=True,
            routing_key=settings.consumer.routing_registration,
        ),
        RabbitQueue(
            name=settings.consumer.queue_request_created,
            durable=True,
            routing_key=settings.consumer.routing_request_created,
        ),
        RabbitQueue(
            name=settings.consumer.queue_request_cancelled,
            durable=True,
            routing_key=settings.consumer.routing_request_cancelled,
        ),
        RabbitQueue(
            name=settings.consumer.queue_request_status,
            durable=True,
            routing_key=settings.consumer.routing_request_status,
        ),
    )

    @broker.subscriber(queues[0])
    async def on_visitor_registered(event: VisitorRegisteredEvent) -> None:
        """Новая регистрация посетителя → уведомление админам."""
        bot = await container.get(Bot)
        text = (
            f"🆕 Новая регистрация в боте:\n"
            f"ФИО: {event.full_name}\n"
            f"Telegram id: {event.telegram_id}"
        )
        await _notify_role(container, bot, UserRole.ADMIN, text)

    @broker.subscriber(queues[1])
    async def on_request_created(event: RequestCreatedEvent) -> None:
        """Новая заявка → уведомление менеджерам объекта."""
        bot = await container.get(Bot)
        text = f"📝 Новая заявка #{event.request_id} на объект «{event.object_name}»."
        await _notify_users(container, bot, event.manager_ids, text)

    @broker.subscriber(queues[2])
    async def on_request_cancelled(event: RequestCancelledEvent) -> None:
        """Отмена заявки → уведомление менеджерам объекта."""
        bot = await container.get(Bot)
        text = f"🚫 Заявка #{event.request_id} отменена посетителем."
        await _notify_users(container, bot, event.manager_ids, text)

    @broker.subscriber(queues[3])
    async def on_request_status_changed(event: RequestStatusChangedEvent) -> None:
        """Смена статуса заявки менеджером → уведомление посетителю."""
        bot = await container.get(Bot)
        template = STATUS_TEXT.get(event.status)
        if template is None:
            return
        try:
            await bot.send_message(
                event.visitor_telegram_id,
                template.format(request_id=event.request_id),
            )
        except TelegramAPIError:
            log.warning(
                "notify_visitor_failed",
                request_id=event.request_id,
                chat_id=event.visitor_telegram_id,
            )


async def _notify_role(
    container: AsyncContainer, bot: Bot, role: UserRole, text: str
) -> None:
    """Разослать текст всем активным пользователям роли с telegram_id."""
    async with container() as scope:
        users = await scope.get(UserRepository)
        chat_ids = await users.list_telegram_ids_by_role(role)
    await _send_all(bot, chat_ids, text)


async def _notify_users(
    container: AsyncContainer, bot: Bot, user_ids: list[int], text: str
) -> None:
    """Разослать текст перечисленным пользователям (менеджерам объекта)."""
    if not user_ids:
        return
    async with container() as scope:
        users = await scope.get(UserRepository)
        chat_ids = await users.list_telegram_ids_by_ids(user_ids)
    await _send_all(bot, chat_ids, text)


async def _send_all(bot: Bot, chat_ids: list[int], text: str) -> None:
    """Отправка сообщений: ошибки по одному чату не прерывают рассылку."""
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
        except TelegramAPIError:
            log.warning("notify_send_failed", chat_id=chat_id)
