"""Роутер аутентификации: login, refresh, logout."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.schemas.auth import LoginIn, LoginOut
from app.domain.models import User
from app.services.auth import ACCESS_COOKIE, REFRESH_COOKIE, AuthError, AuthService
from app.services.security import RateLimiter

router = APIRouter(prefix="/auth", route_class=DishkaRoute, tags=["auth"])


@router.post("/login", response_model=LoginOut)
async def login(
    data: LoginIn,
    request: Request,
    response: Response,
    auth: FromDishka[AuthService],
    limiter: FromDishka[RateLimiter],
) -> User:
    """Вход: httpOnly cookies с access/refresh, регистрация устройства."""
    client_ip = request.client.host if request.client else "unknown"
    if not await limiter.check(f"login:{client_ip}", limit=10, window_seconds=60):
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
