"""Роутер посетителей (только admin): список, поиск, бан/разбан."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.common import Page
from app.api.schemas.visitor import VisitorOut
from app.repository.visitor import VisitorRepository

router = APIRouter(prefix="/visitors", route_class=DishkaRoute, tags=["visitors"])


@router.get("", response_model=Page[VisitorOut])
async def list_visitors(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[VisitorRepository],
    search: str | None = None,
    is_blocked: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> Page[VisitorOut]:
    """Список посетителей с поиском по ФИО и фильтром блокировки."""
    items, total = await repo.list_page(
        search=search,
        is_blocked=is_blocked,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[VisitorOut.model_validate(v) for v in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{visitor_id}", response_model=VisitorOut)
async def get_visitor(
    visitor_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[VisitorRepository],
) -> VisitorOut:
    """Получить посетителя."""
    visitor = await repo.get(visitor_id)
    if visitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor not found")
    return VisitorOut.model_validate(visitor)


@router.post("/{visitor_id}/ban", response_model=VisitorOut)
async def ban_visitor(
    visitor_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[VisitorRepository],
) -> VisitorOut:
    """Заблокировать посетителя."""
    visitor = await repo.get(visitor_id)
    if visitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor not found")
    if not visitor.is_blocked:
        visitor.is_blocked = True
        visitor.blocked_at = datetime.now(timezone.utc)
    return VisitorOut.model_validate(visitor)


@router.post("/{visitor_id}/unban", response_model=VisitorOut)
async def unban_visitor(
    visitor_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[VisitorRepository],
) -> VisitorOut:
    """Разблокировать посетителя."""
    visitor = await repo.get(visitor_id)
    if visitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visitor not found")
    visitor.is_blocked = False
    visitor.blocked_at = None
    return VisitorOut.model_validate(visitor)
