"""Авторизация через dishka (для роутеров с route_class=DishkaRoute).

AuthProvider выдаёт текущего пользователя по access-токену из httpOnly cookie
(проверка blacklist в Redis) и обёртку AdminUser для admin-only эндпоинтов.
"""

from dataclasses import dataclass
from typing import Any

from dishka import Provider, Scope, provide
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User, UserRole
from app.repository.session import SessionRepository
from app.repository.user import UserRepository
from app.services.auth import ACCESS_COOKIE
from app.services.security import TokenBlacklist
from app.services.tokens import TokenError, TokenService

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
)
FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Admin only",
)


def get_or_404(obj: Any, detail: str) -> Any:
    """Объект или 404 (общий паттерн всех CRUD-роутеров).

    Использование: category = get_or_404(await repo.get(id), "Category not found")
    """
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail)
    return obj


async def flush_or_400(session: AsyncSession, detail: str) -> None:
    """flush изменений; нарушение ограничения БД (IntegrityError) → rollback и 400.

    Общий паттерн роутеров: уникальность/FK проверяются БД до формирования
    ответа, а не на commit после него.
    """
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail) from None


@dataclass
class AdminUser:
    """Маркер-обёртка: текущий пользователь с ролью admin."""

    user: User


class AuthProvider(Provider):
    """Пользователь запроса — REQUEST-scope, читается из cookie."""

    @provide(scope=Scope.REQUEST)
    async def provide_current_user(
        self,
        request: Request,
        tokens: TokenService,
        blacklist: TokenBlacklist,
        users: UserRepository,
        sessions: SessionRepository,
    ) -> User:
        """Текущий пользователь по access-токену.

        Сессия (claim sid) должна быть активна: отзыв сессии (админом, сменой
        пароля, logout) сразу делает недействительным и её access-токен.
        """
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise UNAUTHORIZED
        try:
            payload = tokens.decode_access(token)
        except TokenError:
            raise UNAUTHORIZED from None
        if await blacklist.is_blacklisted(payload["jti"]):
            raise UNAUTHORIZED
        sid = payload.get("sid")
        if sid is not None:
            session = await sessions.get(int(sid))
            if session is None or not session.is_active:
                raise UNAUTHORIZED
        user = await users.get(int(payload["sub"]))
        if user is None or not user.is_active:
            raise UNAUTHORIZED
        return user

    @provide(scope=Scope.REQUEST)
    def provide_admin_user(self, user: User) -> AdminUser:
        """Обёртка admin-only (403 для остальных ролей)."""
        if user.role != UserRole.ADMIN:
            raise FORBIDDEN
        return AdminUser(user=user)
