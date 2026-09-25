"""Сервис аутентификации: login, refresh, logout, отзыв сессий.

Токены выдаются в httpOnly cookies на каждое устройство (device_id из thumbmarkjs).
Access и refresh содержат sid — id сессии: отзыв сессии (logout, отзыв админом,
смена пароля) сразу делает недействительными оба токена (проверка в
AuthProvider.provide_current_user). Дополнительно при logout/отзыве jti
заносятся в blacklist в Redis с TTL до истечения.
"""

from datetime import datetime, timezone

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.domain.models import Device, Session, User
from app.log import get_logger
from app.repository.device import DeviceRepository
from app.repository.session import SessionRepository
from app.repository.user import UserRepository
from app.services.password import verify_password_async
from app.services.security import TokenBlacklist
from app.services.tokens import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    TokenService,
)

ACCESS_COOKIE = "ubc_access"
REFRESH_COOKIE = "ubc_refresh"

# Окно, в течение которого повтор только что ротированного refresh считается
# параллельным запросом вкладок (401 без отзыва), а не повтором украденного токена
REFRESH_REUSE_GRACE_SECONDS = 30

log = get_logger(__name__)


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
        # bcrypt выполняется всегда (и для несуществующего пользователя) —
        # время ответа не раскрывает существование username
        password_ok = await verify_password_async(
            password, user.password_hash if user is not None else None
        )
        if user is None or not user.is_active or not password_ok:
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

        # сессия создаётся до токенов: её id попадает в claim sid
        refresh_jti = self.tokens.new_jti()
        session = await self.sessions.add(
            Session(
                device_id=device.id,
                user_id=user.id,
                refresh_token_jti=refresh_jti,
                is_active=True,
                created_at=now,
            )
        )
        pair = self.tokens.create_pair(
            user_id=user.id,
            role=user.role.value,
            session_id=session.id,
            refresh_jti=refresh_jti,
        )
        self._set_cookies(response, pair)
        return user

    async def refresh(self, refresh_token: str | None, response: Response) -> None:
        """Обновить пару токенов (ротация refresh, отзыв старых токенов).

        Повторное использование уже ротированного refresh (вне короткого окна
        параллельных запросов) — признак кражи токена: отзывается вся сессия.
        """
        if not refresh_token:
            raise AuthError("no refresh token")
        try:
            payload = self.tokens.decode_refresh(refresh_token)
        except TokenError as exc:
            raise AuthError("invalid refresh token") from exc

        jti = payload["jti"]
        sid = payload.get("sid")
        if sid is not None:
            # блокировка строки: параллельные refresh ротируют сессию по очереди
            session = await self.sessions.get_for_update(int(sid))
        else:
            session = await self.sessions.get_by_jti(jti)
        if session is None or not session.is_active:
            raise AuthError("session revoked")
        if session.refresh_token_jti != jti:
            if await self.blacklist.is_recently_rotated(jti):
                # параллельный refresh (вкладки/запросы) — новый токен уже выдан
                raise AuthError("refresh token already rotated")
            log.warning(
                "refresh_token_reuse_detected",
                session_id=session.id,
                user_id=session.user_id,
            )
            await self.revoke_session(session)
            raise AuthError("refresh token reuse detected")

        user = await self.users.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthError("user inactive")

        # Отозвать старый refresh до конца его TTL
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await self.blacklist.add(jti, self.tokens.remaining_ttl(exp))
        await self.blacklist.mark_rotated(jti, REFRESH_REUSE_GRACE_SECONDS)

        pair = self.tokens.create_pair(
            user_id=user.id, role=user.role.value, session_id=session.id
        )
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
        """Отозвать одну сессию: refresh-токен в blacklist.

        Access-токены сессии перестают приниматься сразу — AuthProvider
        проверяет активность сессии по claim sid.
        """
        await self.sessions.revoke(session)
        # exp не хранится в БД — берём максимальный срок refresh
        backend = self.settings.backend
        await self.blacklist.add(
            session.refresh_token_jti,
            backend.refresh_token_expire_days * 24 * 3600,
        )

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Отозвать все активные сессии пользователя (refresh-jti в blacklist).

        Используется при удалении пользователя и смене пароля.
        Возвращает количество отозванных сессий.
        """
        active, _total = await self.sessions.list_by_user(
            user_id, only_active=True
        )
        backend = self.settings.backend
        ttl = backend.refresh_token_expire_days * 24 * 3600
        # одним pipeline вместо N round-trip'ов; если Redis недоступен —
        # сессии отзываются в БД: refresh не работает, access отклоняется
        # по неактивной сессии (claim sid) — логируем и продолжаем
        try:
            await self.blacklist.add_many(
                [(s.refresh_token_jti, ttl) for s in active]
            )
        except Exception:
            log.error(
                "blacklist_unavailable_on_revoke_all",
                user_id=user_id,
                exc_info=True,
            )
        return await self.sessions.revoke_all_for_user(user_id)
