"""Тесты хеширования паролей (app.services.password)."""

import pytest

from app.services.password import (
    PasswordError,
    hash_password,
    validate_password_policy,
    verify_password,
)


def test_hash_and_verify_ok():
    password_hash = hash_password("s3cret-password")
    assert password_hash != "s3cret-password"
    assert verify_password("s3cret-password", password_hash)


def test_verify_wrong_password():
    password_hash = hash_password("s3cret-password")
    assert not verify_password("wrong-password", password_hash)


def test_hash_is_salted():
    """Один и тот же пароль даёт разные хеши (соль bcrypt)."""
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_invalid_hash_returns_false():
    """Битый хеш не должен бросать исключение."""
    assert not verify_password("any", "not-a-bcrypt-hash")


class TestPasswordPolicy:
    """Политика пароля: 8–72 байта (bcrypt молча обрезает > 72)."""

    def test_too_short_rejected(self):
        with pytest.raises(PasswordError):
            validate_password_policy("short")

    def test_too_long_rejected(self):
        # 73 байта — bcrypt обрезал бы молча
        with pytest.raises(PasswordError):
            validate_password_policy("x" * 73)

    def test_valid_range_accepted(self):
        validate_password_policy("x" * 8)
        validate_password_policy("x" * 72)

    def test_hash_enforces_policy(self):
        with pytest.raises(PasswordError):
            hash_password("short")
