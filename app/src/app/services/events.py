"""Издатель событий уведомлений (faststream + RabbitMQ).

События публикуются в default exchange по routing_key;
очереди привязываются на стороне потребителя (bot, см. app.bot.notifications).

Routing keys и имена очередей задаются в .env (CONSUMER_ROUTING_*,
CONSUMER_QUEUE_*) — издатель и потребитель должны использовать одинаковые
значения, иначе сообщения возвращаются брокером (Basic.Return, unroutable).
"""

from pydantic import BaseModel
from faststream.rabbit import RabbitBroker

from app.config.settings import Settings


class VisitorRegisteredEvent(BaseModel):
    """Новая регистрация посетителя в боте."""

    visitor_id: int
    telegram_id: int
    full_name: str


class RequestCreatedEvent(BaseModel):
    """Новая заявка посетителя."""

    request_id: int
    object_id: int
    object_name: str
    manager_ids: list[int]
    visitor_telegram_id: int


class RequestCancelledEvent(BaseModel):
    """Отмена заявки посетителем."""

    request_id: int
    object_id: int
    manager_ids: list[int]


class RequestStatusChangedEvent(BaseModel):
    """Менеджер изменил статус заявки (уведомление посетителю)."""

    request_id: int
    visitor_telegram_id: int
    status: str  # RequestStatus.value


class EventPublisher:
    """Публикация событий в RabbitMQ."""

    def __init__(self, broker: RabbitBroker, settings: Settings) -> None:
        self.broker = broker
        consumer = settings.consumer
        self.routing_registration = consumer.routing_registration
        self.routing_request_created = consumer.routing_request_created
        self.routing_request_cancelled = consumer.routing_request_cancelled
        self.routing_request_status = consumer.routing_request_status

    async def publish_visitor_registered(self, event: VisitorRegisteredEvent) -> None:
        await self.broker.publish(event, routing_key=self.routing_registration)

    async def publish_request_created(self, event: RequestCreatedEvent) -> None:
        await self.broker.publish(event, routing_key=self.routing_request_created)

    async def publish_request_cancelled(self, event: RequestCancelledEvent) -> None:
        await self.broker.publish(event, routing_key=self.routing_request_cancelled)

    async def publish_request_status_changed(
        self, event: RequestStatusChangedEvent
    ) -> None:
        await self.broker.publish(event, routing_key=self.routing_request_status)
