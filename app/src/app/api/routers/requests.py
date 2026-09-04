"""Роутер заявок.

- admin видит все заявки (но не обрабатывает);
- менеджер видит заявки по своим объектам и обрабатывает их.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.schemas.common import Page
from app.api.schemas.request import RequestOut, RequestStatusIn
from app.domain.models import RequestStatus, User, UserRole
from app.repository.object import ObjectRepository
from app.repository.request import RequestRepository
from app.services.events import (
    EventPublisher,
    RequestStatusChangedEvent,
)

router = APIRouter(prefix="/requests", route_class=DishkaRoute, tags=["requests"])


async def _visible_object_ids(
    user: User, requests: RequestRepository
) -> list[int] | None:
    """None — все объекты (admin), список — объекты менеджера."""
    if user.role == UserRole.ADMIN:
        return None
    return await requests.list_manager_object_ids(user.id)


@router.get("", response_model=Page[RequestOut])
async def list_requests(
    user: FromDishka[User],
    repo: FromDishka[RequestRepository],
    status_filter: RequestStatus | None = None,
    object_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> Page[RequestOut]:
    """Список заявок (менеджер — только по своим объектам)."""
    object_ids = await _visible_object_ids(user, repo)
    items, total = await repo.list_page(
        object_ids=object_ids,
        status=status_filter,
        object_id=object_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[RequestOut.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=RequestOut)
async def get_request(
    request_id: int,
    user: FromDishka[User],
    repo: FromDishka[RequestRepository],
) -> RequestOut:
    """Получить заявку (с проверкой доступа)."""
    req = await repo.get(request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    object_ids = await _visible_object_ids(user, repo)
    if object_ids is not None and req.object_id not in object_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    return RequestOut.model_validate(req)


@router.post("/{request_id}/status", response_model=RequestOut)
async def change_status(
    request_id: int,
    data: RequestStatusIn,
    user: FromDishka[User],
    repo: FromDishka[RequestRepository],
    objects: FromDishka[ObjectRepository],
    publisher: FromDishka[EventPublisher],
) -> RequestOut:
    """Подтвердить/отклонить заявку (только менеджер объекта).
    Допустимые переходы: new → approved | rejected,
    approved → completed (менеджер объекта).
    """
    req = await repo.get(request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    # доступ: только менеджер, назначенный на объект заявки
    if user.role != UserRole.MANAGER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager only")
    manager_ids = await objects.list_manager_ids(req.object_id)
    if user.id not in manager_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your object")

    allowed = {
        (RequestStatus.NEW, RequestStatus.APPROVED),
        (RequestStatus.NEW, RequestStatus.REJECTED),
        (RequestStatus.APPROVED, RequestStatus.COMPLETED),
    }
    if (req.status, data.status) not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot change status {req.status.value} -> {data.status.value}",
        )
    req.status = data.status
    if data.status == RequestStatus.APPROVED:
        req.confirmed_at = datetime.now(timezone.utc)
    await repo.session.flush()
    # уведомление посетителю в бот (lazy load связи, telegram_id может отсутствовать)
    await repo.session.refresh(req, attribute_names=["visitor"])
    if req.visitor.telegram_id:
        await publisher.publish_request_status_changed(
            RequestStatusChangedEvent(
                request_id=req.id,
                visitor_telegram_id=req.visitor.telegram_id,
                status=req.status.value,
            )
        )
    return RequestOut.model_validate(req)
