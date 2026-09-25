"""Роутер аутентификации: login, refresh, logout."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.schemas.auth import LoginIn, LoginOut
from app.domain.models import User
from app.services.auth import ACCESS_COOKIE, REFRESH_COOKIE, AuthError, AuthService
from app.services.security import RateLimiter

router = APIRouter(prefix="/auth", route_class=TransactionalRoute, tags=["auth"])


# Лимиты попыток входа (фиксированное окно 60 с)
LOGIN_LIMIT_PER_IP_USER = 10
LOGIN_LIMIT_PER_USER = 30
LOGIN_WINDOW_SECONDS = 60
# user_agent пишется в devices.user_agent (String(512))
USER_AGENT_MAX_LENGTH = 512


def _client_ip(request: Request) -> str:
    """Реальный IP клиента: последний адрес X-Forwarded-For или socket-адрес.

    nginx перезаписывает X-Forwarded-For адресом клиента ($remote_addr), а
    при дописывании ($proxy_add_x_forwarded_for) реальный адрес — последний.
    Первые элементы задаёт клиент — им доверять нельзя.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginOut)
async def login(
    data: LoginIn,
    request: Request,
    response: Response,
    auth: FromDishka[AuthService],
    limiter: FromDishka[RateLimiter],
) -> User:
    """Вход: httpOnly cookies с access/refresh, регистрация устройства."""
    client_ip = _client_ip(request)
    # ключ ip+username: не даём одному IP брутфорсить разные аккаунты
    # и не блокируем всех клиентов одного IP при атаке на один аккаунт;
    # ключ username: верхняя граница попыток на аккаунт при смене IP
    allowed_ip = await limiter.check(
        f"login:{client_ip}:{data.username}",
        limit=LOGIN_LIMIT_PER_IP_USER,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    allowed_user = await limiter.check(
        f"login:user:{data.username}",
        limit=LOGIN_LIMIT_PER_USER,
        window_seconds=LOGIN_WINDOW_SECONDS,
    )
    if not (allowed_ip and allowed_user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, try later",
        )
    user_agent = request.headers.get("user-agent")
    try:
        return await auth.login(
            username=data.username,
            password=data.password,
            device_id=data.device_id,
            user_agent=user_agent[:USER_AGENT_MAX_LENGTH] if user_agent else None,
            response=response,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    auth: FromDishka[AuthService],
) -> dict[str, str]:
    """Обновить пару токенов (ротация refresh)."""
    try:
        await auth.refresh(request.cookies.get(REFRESH_COOKIE), response)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return {"status": "ok"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth: FromDishka[AuthService],
) -> dict[str, str]:
    """Выход: оба токена в blacklist, сессия отзывается."""
    await auth.logout(
        request.cookies.get(ACCESS_COOKIE),
        request.cookies.get(REFRESH_COOKIE),
        response,
    )
    return {"status": "ok"}


@router.get("/me", response_model=LoginOut)
async def me(user: FromDishka[User]) -> User:
    """Текущий пользователь по access-токену (роль — с сервера, не из localStorage)."""
    return user
