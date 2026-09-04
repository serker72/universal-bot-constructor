"""Тесты security-сервисов (app.services.security) на фейковом Redis."""

import pytest

from app.services.security import RateLimiter, TokenBlacklist


class FakeRedis:
    """Минимальная заглушка redis.asyncio.Redis для тестов."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttl[key] = ex

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def incr(self, key: str) -> int:
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    async def expire(self, key: str, seconds: int) -> None:
        self.ttl[key] = seconds


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


class TestTokenBlacklist:
    async def test_add_and_check(self, redis):
        blacklist = TokenBlacklist(redis)  # type: ignore[arg-type]
        await blacklist.add("jti-1", ttl_seconds=60)
        assert await blacklist.is_blacklisted("jti-1") is True
        assert await blacklist.is_blacklisted("jti-unknown") is False

    async def test_non_positive_ttl_is_ignored(self, redis):
        """Токен с истёкшим TTL не добавляется в blacklist."""
        blacklist = TokenBlacklist(redis)  # type: ignore[arg-type]
        await blacklist.add("jti-2", ttl_seconds=0)
        assert await blacklist.is_blacklisted("jti-2") is False

    async def test_key_prefix(self, redis):
        blacklist = TokenBlacklist(redis)  # type: ignore[arg-type]
        await blacklist.add("jti-3", ttl_seconds=10)
        assert "auth:blacklist:jti-3" in redis.store
        assert redis.ttl["auth:blacklist:jti-3"] == 10


class TestRateLimiter:
    async def test_allows_within_limit(self, redis):
        limiter = RateLimiter(redis)  # type: ignore[arg-type]
        for _ in range(3):
            assert await limiter.check("ip:1", limit=3, window_seconds=60)

    async def test_blocks_over_limit(self, redis):
        limiter = RateLimiter(redis)  # type: ignore[arg-type]
        for _ in range(3):
            await limiter.check("ip:1", limit=3, window_seconds=60)
        assert await limiter.check("ip:1", limit=3, window_seconds=60) is False

    async def test_keys_are_independent(self, redis):
        limiter = RateLimiter(redis)  # type: ignore[arg-type]
        await limiter.check("ip:1", limit=1, window_seconds=60)
        assert await limiter.check("ip:1", limit=1, window_seconds=60) is False
        assert await limiter.check("ip:2", limit=1, window_seconds=60) is True

    async def test_window_ttl_set_on_first_request(self, redis):
        limiter = RateLimiter(redis)  # type: ignore[arg-type]
        await limiter.check("ip:1", limit=10, window_seconds=30)
        assert redis.ttl["auth:ratelimit:ip:1"] == 30
