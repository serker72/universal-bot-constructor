"""Провайдер Redis (redis-py async)."""

from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from app.config.settings import Settings


class RedisProvider(Provider):
    """Клиент Redis как синглтон приложения."""

    @provide(scope=Scope.APP)
    async def provide_redis(self, settings: Settings) -> AsyncIterator[Redis]:
        client = Redis.from_url(settings.redis.url)
        yield client
        await client.aclose()
