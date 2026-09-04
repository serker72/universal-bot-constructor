"""Авторизация через dishka (для роутеров с route_class=DishkaRoute).

AuthProvider выдаёт текущего пользователя по access-токену из httpOnly cookie
(проверка blacklist в Redis) и обёртку AdminUser для admin-only эндпоинтов.
"""

from dataclasses import dataclass

from dishka import Provider, Scope, provide
from fastapi import HTTPException, Request, status

from app.domain.models import User, UserRole
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
    ) -> User:
        """Текущий пользователь по access-токену."""
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise UNAUTHORIZED
        try:
            payload = tokens.decode_access(token)
        except TokenError:
            raise UNAUTHORIZED from None
        if await blacklist.is_blacklisted(payload["jti"]):
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
