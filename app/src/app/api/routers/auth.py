"""Роутер аутентификации: login, refresh, logout."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.schemas.auth import LoginIn, LoginOut
from app.domain.models import User
from app.services.auth import ACCESS_COOKIE, REFRESH_COOKIE, AuthError, AuthService
from app.services.security import RateLimiter

router = APIRouter(prefix="/auth", route_class=DishkaRoute, tags=["auth"])


def _client_ip(request: Request) -> str:
    """Реальный IP клиента: первый X-Forwarded-For (nginx) или socket-адрес."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
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
    # и не блокируем всех клиентов одного IP при атаке на один аккаунт
    if not await limiter.check(
        f"login:{client_ip}:{data.username}", limit=10, window_seconds=60
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, try later",
        )
    try:
        return await auth.login(
            username=data.username,
            password=data.password,
            device_id=data.device_id,
            user_agent=request.headers.get("user-agent"),
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
