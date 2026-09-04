"""Провайдер брокера RabbitMQ (faststream)."""

from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from faststream.rabbit import RabbitBroker

from app.config.settings import Settings


class BrokerProvider(Provider):
    """Брокер как синглтон.

    Старт выполняется отдельно (broker.start() в bot/main.py / api/main.py)
    ПОСЛЕ регистрации подписчиков: подписчики, добавленные после старта,
    не создают очередей (faststream 0.7).
    """

    @provide(scope=Scope.APP)
    async def provide_broker(self, settings: Settings) -> AsyncIterator[RabbitBroker]:
        broker = RabbitBroker(settings.rabbitmq.url)
        yield broker
        await broker.stop()
