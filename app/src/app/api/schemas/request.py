"""Схемы заявок."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.request_field import RequestFieldValueOut
from app.domain.models import RequestStatus


class RequestOut(BaseModel):
    """Заявка (динамические поля — в fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    visitor_id: int
    object_id: int
    phone: str
    fields: list[RequestFieldValueOut] = Field(default_factory=list)
    status: RequestStatus
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RequestStatusIn(BaseModel):
    """Смена статуса заявки."""

    status: RequestStatus
