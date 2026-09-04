"""Сервис аутентификации: login, refresh, logout, отзыв сессий.

Токены выдаются в httpOnly cookies на каждое устройство (device_id из thumbmarkjs).
При logout/отзыве оба токена заносятся в blacklist в Redis с TTL до истечения.
"""

from datetime import datetime, timezone

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.domain.models import Device, Session, User
from app.repository.device import DeviceRepository
from app.repository.session import SessionRepository
from app.repository.user import UserRepository
from app.services.password import verify_password
from app.services.security import TokenBlacklist
from app.services.tokens import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    TokenService,
)

ACCESS_COOKIE = "ubc_access"
REFRESH_COOKIE = "ubc_refresh"


class AuthError(Exception):
    """Ошибка аутентификации (неверные данные, сессия отозвана)."""


class AuthService:
    """Управление входом, refresh и logout."""

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        users: UserRepository,
        devices: DeviceRepository,
        sessions: SessionRepository,
        tokens: TokenService,
        blacklist: TokenBlacklist,
    ) -> None:
        self.settings = settings
        self.session = session
        self.users = users
        self.devices = devices
        self.sessions = sessions
        self.tokens = tokens
        self.blacklist = blacklist

    # -- cookies ------------------------------------------------------------

    def _set_cookies(self, response: Response, pair) -> None:  # noqa: ANN001
        """Установить httpOnly cookies с токенами."""
        backend = self.settings.backend
        common = {
            "httponly": True,
            "secure": backend.cookie_secure,
            "samesite": "lax",
            "domain": backend.cookie_domain,
            "path": "/",
        }
        response.set_cookie(
            ACCESS_COOKIE,
            pair.access_token,
            max_age=int(
                backend.access_token_expire_minutes * 60
            ),
            **common,
        )
        response.set_cookie(
            REFRESH_COOKIE,
            pair.refresh_token,
            max_age=int(backend.refresh_token_expire_days * 24 * 3600),
            **common,
        )

    def _clear_cookies(self, response: Response) -> None:
        """Удалить cookies с токенами."""
        backend = self.settings.backend
        for name in (ACCESS_COOKIE, REFRESH_COOKIE):
            response.delete_cookie(
                name,
                domain=backend.cookie_domain,
                path="/",
                httponly=True,
                secure=backend.cookie_secure,
                samesite="lax",
            )

    # -- операции -----------------------------------------------------------

    async def login(
        self,
        *,
        username: str,
        password: str,
        device_id: str,
        user_agent: str | None,
        response: Response,
    ) -> User:
        """Вход: проверка пароля, регистрация устройства, выдача токенов."""
        user = await self.users.get_by_username(username)
        if user is None or not user.is_active:
            raise AuthError("invalid credentials")
        if not verify_password(password, user.password_hash):
            raise AuthError("invalid credentials")

        now = datetime.now(timezone.utc)
        device = await self.devices.get_by_device_id(user.id, device_id)
        if device is None:
            device = Device(
                user_id=user.id,
                device_id=device_id,
                user_agent=user_agent,
                created_at=now,
                last_seen_at=now,
            )
            await self.devices.add(device)
        else:
            device.user_agent = user_agent or device.user_agent
            await self.devices.touch(device)

        pair = self.tokens.create_pair(user_id=user.id, role=user.role.value)
        await self.sessions.add(
            Session(
                device_id=device.id,
                user_id=user.id,
                refresh_token_jti=pair.refresh_jti,
                is_active=True,
                created_at=now,
            )
        )
        self._set_cookies(response, pair)
        return user

    async def refresh(self, refresh_token: str | None, response: Response) -> None:
        """Обновить пару токенов (ротация refresh, отзыв старых токенов)."""
        if not refresh_token:
            raise AuthError("no refresh token")
        try:
            payload = self.tokens.decode_refresh(refresh_token)
        except TokenError as exc:
            raise AuthError("invalid refresh token") from exc

        jti = payload["jti"]
        session = await self.sessions.get_by_jti(jti)
        if session is None or not session.is_active:
            raise AuthError("session revoked")

        user = await self.users.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthError("user inactive")

        # Отозвать старые токены (refresh до конца TTL, access — по exp из payload)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await self.blacklist.add(
            jti, self.tokens.remaining_ttl(exp)
        )

        pair = self.tokens.create_pair(user_id=user.id, role=user.role.value)
        # Ротация: сессия продолжает жить с новым jti refresh
        session.refresh_token_jti = pair.refresh_jti
        self._set_cookies(response, pair)

    async def logout(
        self,
        access_token: str | None,
        refresh_token: str | None,
        response: Response,
    ) -> None:
        """Выход: оба токена в blacklist, деактивация сессии."""
        for token, expected_type in (
            (access_token, TOKEN_TYPE_ACCESS),
            (refresh_token, TOKEN_TYPE_REFRESH),
        ):
            if not token:
                continue
            try:
                payload = (
                    self.tokens.decode_access(token)
                    if expected_type == TOKEN_TYPE_ACCESS
                    else self.tokens.decode_refresh(token)
                )
            except TokenError:
                continue
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            await self.blacklist.add(
                payload["jti"], self.tokens.remaining_ttl(exp)
            )
            if expected_type == TOKEN_TYPE_REFRESH:
                session = await self.sessions.get_by_jti(payload["jti"])
                if session is not None and session.is_active:
                    await self.sessions.revoke(session)
        self._clear_cookies(response)

    async def revoke_session(self, session: Session) -> None:
        """Отозвать одну сессию: refresh-токен в blacklist."""
        await self.sessions.revoke(session)
        # exp не хранится в БД — берём максимальный срок refresh
        backend = self.settings.backend
        await self.blacklist.add(
            session.refresh_token_jti,
            backend.refresh_token_expire_days * 24 * 3600,
        )

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Отозвать все активные сессии пользователя (refresh-jti в blacklist).

        Возвращает количество отозванных сессий.
        """
        active = await self.sessions.list_by_user(user_id, only_active=True)
        backend = self.settings.backend
        ttl = backend.refresh_token_expire_days * 24 * 3600
        for s in active:
            await self.blacklist.add(s.refresh_token_jti, ttl)
        return await self.sessions.revoke_all_for_user(user_id)
