"""Схемы устройств."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceOut(BaseModel):
    """Устройство."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_id: str
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime
