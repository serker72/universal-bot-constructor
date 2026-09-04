"""Health-check роутер.

/health — liveness (процесс жив, без внешних зависимостей);
/health/ready — readiness (проверяет соединение с БД через DI).
"""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dishka.integrations.fastapi import DishkaRoute, FromDishka

router = APIRouter(route_class=DishkaRoute, tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness-проверка."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(session: FromDishka[AsyncSession]) -> dict[str, str]:
    """Readiness-проверка: доступность БД."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
