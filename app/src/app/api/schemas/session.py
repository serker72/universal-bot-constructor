"""Схемы сессий."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionOut(BaseModel):
    """Сессия."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    user_id: int
    refresh_token_jti: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None
