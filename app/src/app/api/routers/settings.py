"""Роутер настроек системы (только admin)."""

from fastapi import APIRouter, HTTPException, status
from dishka.integrations.fastapi import DishkaRoute, FromDishka

from app.api.deps import AdminUser
from app.api.schemas.setting import SettingsIn, SettingsOut
from app.services.app_settings import (
    KEY_CANCEL_INTERVAL_HOURS,
    KEY_CONSENT_TEXT,
    KEY_PAGE_SIZE,
    KEY_WELCOME_TEXT,
    AppSettingsService,
)

ALLOWED_KEYS = {
    KEY_PAGE_SIZE,
    KEY_CANCEL_INTERVAL_HOURS,
    KEY_CONSENT_TEXT,
    KEY_WELCOME_TEXT,
}

router = APIRouter(prefix="/settings", route_class=DishkaRoute, tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings(
    _admin: FromDishka[AdminUser],
    service: FromDishka[AppSettingsService],
) -> SettingsOut:
    """Все настройки системы."""
    return SettingsOut(settings=await service.repo.get_all())


@router.put("", response_model=SettingsOut)
async def update_settings(
    data: SettingsIn,
    _admin: FromDishka[AdminUser],
    service: FromDishka[AppSettingsService],
) -> SettingsOut:
    """Обновить настройки (частично, только известные ключи)."""
    unknown = set(data.settings) - ALLOWED_KEYS
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown settings keys: {', '.join(sorted(unknown))}",
        )
    for key, value in data.settings.items():
        await service.set(key, value)
    return SettingsOut(settings=await service.repo.get_all())
