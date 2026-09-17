"""Схемы заявок."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.domain.models import RequestStatus


class RequestOut(BaseModel):
    """Заявка."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    visitor_id: int
    object_id: int
    phone: str
    comment: str | None
    start_date: date | None
    start_time: time | None
    end_date: date | None
    end_time: time | None
    status: RequestStatus
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RequestStatusIn(BaseModel):
    """Смена статуса заявки."""

    status: RequestStatus
