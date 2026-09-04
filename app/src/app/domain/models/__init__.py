"""Модели SQLAlchemy. Импортируются все, чтобы alembic видел метаданные."""

from app.domain.models.category import Category
from app.domain.models.device import Device
from app.domain.models.object import Object
from app.domain.models.object_manager import ObjectManager
from app.domain.models.request import Request, RequestStatus
from app.domain.models.session import Session
from app.domain.models.setting import Setting
from app.domain.models.user import User, UserRole
from app.domain.models.visitor import Visitor

__all__ = [
    "Category",
    "Device",
    "Object",
    "ObjectManager",
    "Request",
    "RequestStatus",
    "Session",
    "Setting",
    "User",
    "UserRole",
    "Visitor",
]
