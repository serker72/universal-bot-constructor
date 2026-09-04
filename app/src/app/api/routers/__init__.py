"""Роутеры API."""

from app.api.routers.auth import router as auth_router
from app.api.routers.categories import router as categories_router
from app.api.routers.devices import router as devices_router
from app.api.routers.objects import router as objects_router
from app.api.routers.pdf import router as pdf_router
from app.api.routers.requests import router as requests_router
from app.api.routers.sessions import router as sessions_router
from app.api.routers.settings import router as settings_router
from app.api.routers.users import router as users_router
from app.api.routers.visitors import router as visitors_router

__all__ = [
    "auth_router",
    "categories_router",
    "devices_router",
    "objects_router",
    "pdf_router",
    "requests_router",
    "sessions_router",
    "settings_router",
    "users_router",
    "visitors_router",
]
