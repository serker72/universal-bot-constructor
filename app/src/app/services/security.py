"""Сервисы безопасности на Redis: blacklist JWT и rate-limit."""

from redis.asyncio import Redis

BLACKLIST_PREFIX = "auth:blacklist:"
RATELIMIT_PREFIX = "auth:ratelimit:"
ROTATED_PREFIX = "auth:rotated:"

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

    async def mark_rotated(self, jti: str, grace_seconds: int) -> None:
        """Отметить refresh-jti как только что ротированный (окно параллельных refresh)."""
        if grace_seconds > 0:
            await self.redis.set(ROTATED_PREFIX + jti, "1", ex=grace_seconds)

    async def is_recently_rotated(self, jti: str) -> bool:
        """jti ротирован в пределах окна (параллельный refresh, а не повтор украденного)."""
        return bool(await self.redis.exists(ROTATED_PREFIX + jti))


class RateLimiter:
    """Rate-limit по фиксированному окну (атомарный INCR + EXPIRE через Lua)."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        # register_script: EVALSHA (скрипт не передаётся на каждый вызов),
        # при NOSCRIPT redis-py сам загружает его повторно
        self._script = redis.register_script(_RATELIMIT_LUA)

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Разрешён ли запрос: не более limit за window_seconds.

        True — разрешено (счётчик увеличен), False — лимит исчерпан.
        """
        full_key = RATELIMIT_PREFIX + key
        count = await self._script(keys=[full_key], args=[window_seconds])
        return int(count) <= limit
