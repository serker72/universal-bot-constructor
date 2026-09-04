"""Схемы посетителей."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VisitorOut(BaseModel):
    """Посетитель."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    full_name: str
    consent_given: bool
    consent_at: datetime | None
    is_blocked: bool
    blocked_at: datetime | None
    created_at: datetime
    updated_at: datetime
