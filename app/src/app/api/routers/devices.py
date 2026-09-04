"""Роутер устройств (только admin)."""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.common import Page
from app.api.schemas.device import DeviceOut
from app.repository.device import DeviceRepository

router = APIRouter(prefix="/devices", route_class=DishkaRoute, tags=["devices"])


@router.get("", response_model=Page[DeviceOut])
async def list_devices(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[DeviceRepository],
    user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Page[DeviceOut]:
    """Список устройств (фильтр по пользователю)."""
    from app.domain.models import Device

    conditions = []
    if user_id is not None:
        conditions.append(Device.user_id == user_id)
    items = await repo.find(*conditions, limit=limit, offset=offset)
    total = await repo.count(*conditions)
    return Page(
        items=[DeviceOut.model_validate(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: int,
    _admin: FromDishka[AdminUser],
    repo: FromDishka[DeviceRepository],
) -> DeviceOut:
    """Получить устройство."""
    device = await repo.get(device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return DeviceOut.model_validate(device)
