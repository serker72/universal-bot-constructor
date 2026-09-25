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
    """Политика пароля: 10+ символов, ≤ 72 байт (bcrypt молча обрезает > 72),
    не из списка распространённых."""

    def test_too_short_rejected(self):
        with pytest.raises(PasswordError):
            validate_password_policy("short")

    def test_too_long_rejected(self):
        # 73 байта — bcrypt обрезал бы молча
        with pytest.raises(PasswordError):
            validate_password_policy("x" * 73)

    def test_valid_range_accepted(self):
        validate_password_policy("x" * 10)
        validate_password_policy("x" * 72)

    def test_nine_chars_rejected(self):
        with pytest.raises(PasswordError):
            validate_password_policy("x" * 9)

    def test_cyrillic_over_72_bytes_rejected(self):
        # 40 кириллических символов = 80 байт UTF-8
        with pytest.raises(PasswordError, match="72 байт"):
            validate_password_policy("ж" * 40)

    def test_common_password_rejected(self):
        with pytest.raises(PasswordError, match="распространён"):
            validate_password_policy("Password123")

    def test_hash_enforces_policy(self):
        with pytest.raises(PasswordError):
            hash_password("short")


async def test_async_wrappers():
    """async-обёртки (to_thread) дают тот же результат; None — хеш-заглушка."""
    from app.services.password import hash_password_async, verify_password_async

    password_hash = await hash_password_async("s3cret-password")
    assert await verify_password_async("s3cret-password", password_hash)
    assert not await verify_password_async("wrong-password", password_hash)
    assert not await verify_password_async("s3cret-password", None)
