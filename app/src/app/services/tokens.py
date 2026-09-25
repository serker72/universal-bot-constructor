"""Сервис JWT-токенов (access + refresh).

Токены содержат: sub (user id), role, jti, тип (access/refresh), exp,
sid (id сессии в таблице sessions — отзыв сессии отзывает и access).
jti refresh-токена хранится в таблице sessions (привязка к устройству).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config.settings import Settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenError(Exception):
    """Токен невалиден (истёк, неверная подпись, неверный тип)."""


class TokenPair:
    """Пара access/refresh с их jti и временем жизни."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        access_jti: str,
        refresh_jti: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_jti = access_jti
        self.refresh_jti = refresh_jti
        self.access_expires_at = access_expires_at
        self.refresh_expires_at = refresh_expires_at


class TokenService:
    """Создание и разбор JWT."""

    def __init__(self, settings: Settings) -> None:
        self.secret = settings.backend.jwt_secret
        self.algorithm = settings.backend.jwt_algorithm
        self.access_ttl = timedelta(
            minutes=settings.backend.access_token_expire_minutes
        )
        self.refresh_ttl = timedelta(days=settings.backend.refresh_token_expire_days)

    def _encode(
        self,
        *,
        token_type: str,
        user_id: int,
        role: str,
        jti: str,
        expires_at: datetime,
        session_id: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "role": role,
            "type": token_type,
            "jti": jti,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }
        if session_id is not None:
            payload["sid"] = session_id
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def _decode(self, token: str, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc
        if payload.get("type") != expected_type:
            raise TokenError("invalid token type")
        return payload

    @staticmethod
    def _expires(ttl: timedelta) -> datetime:
        return datetime.now(timezone.utc) + ttl

    @staticmethod
    def new_jti() -> str:
        """Новый идентификатор токена."""
        return uuid.uuid4().hex

    def create_pair(
        self,
        *,
        user_id: int,
        role: str,
        session_id: int | None = None,
        refresh_jti: str | None = None,
    ) -> TokenPair:
        """Создать пару access/refresh для пользователя.

        session_id — id сессии (claim sid) для проверки активности сессии;
        refresh_jti — заранее сгенерированный jti (сессия создаётся до токенов).
        """
        access_jti = self.new_jti()
        refresh_jti = refresh_jti or self.new_jti()
        access_exp = self._expires(self.access_ttl)
        refresh_exp = self._expires(self.refresh_ttl)
        return TokenPair(
            access_token=self._encode(
                token_type=TOKEN_TYPE_ACCESS,
                user_id=user_id,
                role=role,
                jti=access_jti,
                expires_at=access_exp,
                session_id=session_id,
            ),
            refresh_token=self._encode(
                token_type=TOKEN_TYPE_REFRESH,
                user_id=user_id,
                role=role,
                jti=refresh_jti,
                expires_at=refresh_exp,
                session_id=session_id,
            ),
            access_jti=access_jti,
            refresh_jti=refresh_jti,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    def decode_access(self, token: str) -> dict[str, Any]:
        """Разобрать access-токен (или TokenError)."""
        return self._decode(token, TOKEN_TYPE_ACCESS)

    def decode_refresh(self, token: str) -> dict[str, Any]:
        """Разобрать refresh-токен (или TokenError)."""
        return self._decode(token, TOKEN_TYPE_REFRESH)

    @staticmethod
    def remaining_ttl(expires_at: datetime) -> int:
        """Оставшееся время жизни токена в секундах (>= 0)."""
        return max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
