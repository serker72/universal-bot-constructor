"""Тесты pydantic-схем API (app.api.schemas)."""

import pytest
from pydantic import ValidationError

from app.api.schemas.auth import LoginIn
from app.api.schemas.user import UserIn, UserUpdateIn


class TestUserIn:
    def test_valid(self):
        user = UserIn(username="admin", password="password123", role="admin")
        assert user.username == "admin"
        assert user.role.value == "admin"
        assert user.is_active is True
        assert user.telegram_id is None

    def test_default_role_is_manager(self):
        user = UserIn(username="manager", password="password123")
        assert user.role.value == "manager"

    @pytest.mark.parametrize("username", ["ab", "", "x" * 256])
    def test_username_length(self, username):
        with pytest.raises(ValidationError):
            UserIn(username=username, password="password123")

    @pytest.mark.parametrize("password", ["short", "", "x" * 129])
    def test_password_length(self, password):
        with pytest.raises(ValidationError):
            UserIn(username="admin", password=password)


class TestUserUpdateIn:
    def test_all_optional(self):
        data = UserUpdateIn()
        assert data.password is None
        assert data.role is None
        assert data.telegram_id is None
        assert data.is_active is None

    def test_partial_update(self):
        data = UserUpdateIn(is_active=False)
        assert data.is_active is False
        assert data.password is None

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            UserUpdateIn(role="superuser")


class TestLoginIn:
    def test_valid(self):
        data = LoginIn(username="admin", password="pass", device_id="device-1234")
        assert data.device_id == "device-1234"

    def test_device_id_too_short(self):
        with pytest.raises(ValidationError):
            LoginIn(username="admin", password="pass", device_id="short")
