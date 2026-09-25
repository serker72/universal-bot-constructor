"""Роутер устройств (только admin)."""

from fastapi import APIRouter
from dishka.integrations.fastapi import FromDishka

from app.api.routing import TransactionalRoute
from app.api.deps import AdminUser, get_or_404
from app.api.schemas.common import LimitQuery, OffsetQuery, Page
from app.api.schemas.device import DeviceOut
from app.domain.models import Device
from app.repository.device import DeviceRepository

router = APIRouter(prefix="/devices", route_class=TransactionalRoute, tags=["devices"])


@router.get("", response_model=Page[DeviceOut])
async def list_devices(
    _admin: FromDishka[AdminUser],
    repo: FromDishka[DeviceRepository],
    user_id: int | None = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> Page[DeviceOut]:
    """Список устройств (фильтр по пользователю)."""
    conditions = []
    if user_id is not None:
        conditions.append(Device.user_id == user_id)
    items = await repo.find(
        *conditions, limit=limit, offset=offset, order_by=Device.id
    )
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
    device = get_or_404(await repo.get(device_id), "Device not found")
    return DeviceOut.model_validate(device)
