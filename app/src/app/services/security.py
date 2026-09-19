"""Сервисы безопасности на Redis: blacklist JWT и rate-limit."""

from redis.asyncio import Redis

BLACKLIST_PREFIX = "auth:blacklist:"
RATELIMIT_PREFIX = "auth:ratelimit:"

# Атомарный INCR + EXPIRE (Lua): между операциями не может потеряться TTL
# (иначе при падении процесса ключ остаётся в Redis навсегда → вечный 429).
_RATELIMIT_LUA = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class TokenBlacklist:
    """Чёрный список JWT (access и refresh) с TTL до истечения токена."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def add(self, jti: str, ttl_seconds: int) -> None:
        """Добавить токен в blacklist на время его оставшегося TTL."""
        if ttl_seconds > 0:
            await self.redis.set(BLACKLIST_PREFIX + jti, "1", ex=ttl_seconds)

    async def add_many(self, items: list[tuple[str, int]]) -> None:
        """Добавить несколько токенов одним pipeline (один round-trip)."""
        if not items:
            return
        async with self.redis.pipeline(transaction=False) as pipe:
            for jti, ttl_seconds in items:
                if ttl_seconds > 0:
                    pipe.set(BLACKLIST_PREFIX + jti, "1", ex=ttl_seconds)
            await pipe.execute()

    async def is_blacklisted(self, jti: str) -> bool:
        """Проверить, отозван ли токен."""
        return bool(await self.redis.exists(BLACKLIST_PREFIX + jti))


class RateLimiter:
    """Rate-limit по фиксированному окну (атомарный INCR + EXPIRE через Lua)."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Разрешён ли запрос: не более limit за window_seconds.

        True — разрешено (счётчик увеличен), False — лимит исчерпан.
        """
        full_key = RATELIMIT_PREFIX + key
        count = await self.redis.eval(
            _RATELIMIT_LUA, 1, full_key, window_seconds
        )
        return int(count) <= limit
