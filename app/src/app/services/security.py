"""Сервисы безопасности на Redis: blacklist JWT и rate-limit."""

from redis.asyncio import Redis

BLACKLIST_PREFIX = "auth:blacklist:"
RATELIMIT_PREFIX = "auth:ratelimit:"


class TokenBlacklist:
    """Чёрный список JWT (access и refresh) с TTL до истечения токена."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def add(self, jti: str, ttl_seconds: int) -> None:
        """Добавить токен в blacklist на время его оставшегося TTL."""
        if ttl_seconds > 0:
            await self.redis.set(BLACKLIST_PREFIX + jti, "1", ex=ttl_seconds)

    async def is_blacklisted(self, jti: str) -> bool:
        """Проверить, отозван ли токен."""
        return bool(await self.redis.exists(BLACKLIST_PREFIX + jti))


class RateLimiter:
    """Простой rate-limit по фиксированному окну (INCR + EXPIRE)."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Разрешён ли запрос: не более limit за window_seconds.

        True — разрешено (счётчик увеличен), False — лимит исчерпан.
        """
        full_key = RATELIMIT_PREFIX + key
        count = await self.redis.incr(full_key)
        if count == 1:
            await self.redis.expire(full_key, window_seconds)
        return count <= limit
