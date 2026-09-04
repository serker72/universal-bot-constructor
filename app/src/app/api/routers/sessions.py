"""Роутер сессий (только admin): список, отзыв одной/всех."""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.common import Page
from app.api.schemas.session import SessionOut
from app.domain.models import Session
from app.repository.session import SessionRepository
from app.services.auth import AuthService

router = APIRouter(prefix="/sessions", route_class=DishkaRoute, tags=["sessions"])


@router.get("", response_model=Page[SessionOut])
async def list_sessions(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[SessionRepository],
    user_id: int | None = None,
    only_active: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Page[SessionOut]:
    """Список сессий (фильтр по пользователю, только активные)."""
    if user_id is not None:
        items = await repo.list_by_user(user_id, only_active=only_active)
        total = len(items)
        page = items[offset : offset + limit]
    else:
        conditions = []
        if only_active:
            conditions.append(Session.is_active.is_(True))
        page = await repo.find(*conditions, limit=limit, offset=offset)
        total = await repo.count(*conditions)
    return Page(
        items=[SessionOut.model_validate(s) for s in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{session_id}/revoke", response_model=SessionOut)
async def revoke_session(
    session_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[SessionRepository],
    auth: FromDishka[AuthService],
) -> SessionOut:
    """Отозвать одну сессию (refresh-токен в blacklist)."""
    session = await repo.get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.is_active:
        await auth.revoke_session(session)
    return SessionOut.model_validate(session)


@router.post("/users/{user_id}/revoke-all")
async def revoke_all_sessions(
    user_id: int,
    _admin: FromDishka[AdminUser],
    auth: FromDishka[AuthService],
) -> dict[str, int]:
    """Отозвать все сессии пользователя (refresh-токены в blacklist)."""
    count = await auth.revoke_all_for_user(user_id)
    return {"revoked": count}
