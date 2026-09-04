"""Pydantic-схемы API."""

from app.api.schemas.auth import LoginIn, LoginOut
from app.api.schemas.category import CategoryIn, CategoryOut
from app.api.schemas.common import Page
from app.api.schemas.device import DeviceOut
from app.api.schemas.object import ObjectIn, ObjectOut, ObjectManagersIn, ObjectManagersOut
from app.api.schemas.request import RequestOut, RequestStatusIn
from app.api.schemas.session import SessionOut
from app.api.schemas.setting import SettingsOut, SettingsIn
from app.api.schemas.user import UserIn, UserOut, UserUpdateIn
from app.api.schemas.visitor import VisitorOut

__all__ = [
    "DeviceOut",
    "LoginIn",
    "LoginOut",
    "ObjectIn",
    "ObjectManagersIn",
    "ObjectManagersOut",
    "ObjectOut",
    "Page",
    "RequestOut",
    "RequestStatusIn",
    "SessionOut",
    "SettingsIn",
    "SettingsOut",
    "CategoryIn",
    "CategoryOut",
    "UserIn",
    "UserOut",
    "UserUpdateIn",
    "VisitorOut",
]
