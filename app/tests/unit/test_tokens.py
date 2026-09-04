"""Тесты JWT-токенов (app.services.tokens)."""

from datetime import timedelta

import pytest

from app.config.settings import Settings
from app.services.tokens import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    TokenService,
)


@pytest.fixture
def service(settings) -> TokenService:
    return TokenService(settings)


def test_create_pair_and_decode_access(service: TokenService):
    pair = service.create_pair(user_id=42, role="admin")

    assert pair.access_jti != pair.refresh_jti
    assert pair.access_expires_at < pair.refresh_expires_at

    payload = service.decode_access(pair.access_token)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["jti"] == pair.access_jti


def test_decode_refresh(service: TokenService):
    pair = service.create_pair(user_id=1, role="manager")

    payload = service.decode_refresh(pair.refresh_token)
    assert payload["type"] == TOKEN_TYPE_REFRESH
    assert payload["jti"] == pair.refresh_jti


def test_access_token_rejected_as_refresh(service: TokenService):
    """Access-токен не проходит проверку как refresh (и наоборот)."""
    pair = service.create_pair(user_id=1, role="admin")

    with pytest.raises(TokenError):
        service.decode_refresh(pair.access_token)
    with pytest.raises(TokenError):
        service.decode_access(pair.refresh_token)


def test_invalid_token_raises(service: TokenService):
    with pytest.raises(TokenError):
        service.decode_access("garbage.token.value")


def test_token_signed_with_other_secret(service: TokenService, monkeypatch):
    pair = service.create_pair(user_id=1, role="admin")

    monkeypatch.setenv("BACKEND_JWT_SECRET", "another-secret-0123456789abcdef0123456789")
    other = TokenService(Settings())
    with pytest.raises(TokenError):
        other.decode_access(pair.access_token)


def test_expired_token_raises(service: TokenService, monkeypatch):
    monkeypatch.setattr(service, "access_ttl", timedelta(seconds=-10))
    pair = service.create_pair(user_id=1, role="admin")
    with pytest.raises(TokenError):
        service.decode_access(pair.access_token)


def test_remaining_ttl(service: TokenService):
    from datetime import datetime, timezone

    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    ttl = service.remaining_ttl(future)
    assert 200 < ttl <= 300

    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert service.remaining_ttl(past) == 0

