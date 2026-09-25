"""Издатель событий уведомлений (faststream + RabbitMQ).

События публикуются в явный direct-exchange (CONSUMER_EXCHANGE) по routing
key (CONSUMER_ROUTING_*); очереди (CONSUMER_QUEUE_*) привязываются к exchange
теми же ключами на стороне потребителя (bot, см. app.bot.notifications).
Имя очереди и routing key независимы: смена любого из них не теряет сообщения,
пока издатель и потребитель читают одни и те же переменные.
"""

from pydantic import BaseModel
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from app.config.settings import Settings


def notify_exchange(settings: Settings) -> RabbitExchange:
    """Exchange уведомлений (общий для издателя и потребителя)."""
    return RabbitExchange(
        settings.consumer.exchange, type=ExchangeType.DIRECT, durable=True
    )


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
        self.exchange = notify_exchange(settings)
        consumer = settings.consumer
        self.routing_registration = consumer.routing_registration
        self.routing_request_created = consumer.routing_request_created
        self.routing_request_cancelled = consumer.routing_request_cancelled
        self.routing_request_status = consumer.routing_request_status

    async def _publish(self, event: BaseModel, routing_key: str) -> None:
        await self.broker.publish(
            event, routing_key=routing_key, exchange=self.exchange
        )

    async def publish_visitor_registered(self, event: VisitorRegisteredEvent) -> None:
        await self._publish(event, self.routing_registration)

    async def publish_request_created(self, event: RequestCreatedEvent) -> None:
        await self._publish(event, self.routing_request_created)

    async def publish_request_cancelled(self, event: RequestCancelledEvent) -> None:
        await self._publish(event, self.routing_request_cancelled)

    async def publish_request_status_changed(
        self, event: RequestStatusChangedEvent
    ) -> None:
        await self._publish(event, self.routing_request_status)
