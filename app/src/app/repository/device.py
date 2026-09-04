"""Репозиторий устройств."""

from collections.abc import Sequence
from datetime import datetime, timezone

from app.domain.models import Device
from app.repository.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    model = Device

    async def get_by_device_id(self, user_id: int, device_id: str) -> Device | None:
        """Устройство пользователя по строковому идентификатору (thumbmarkjs)."""
        return await self.find_one(
            Device.user_id == user_id,
            Device.device_id == device_id,
        )

    async def list_by_user(self, user_id: int) -> Sequence[Device]:
        """Устройства пользователя."""
        return await self.find(
            Device.user_id == user_id,
            order_by=Device.last_seen_at.desc(),
        )

    async def touch(self, device: Device) -> Device:
        """Обновить время последнего входа."""
        device.last_seen_at = datetime.now(timezone.utc)
        return device
