"""Тесты хеширования паролей (app.services.password)."""

from app.services.password import hash_password, verify_password


def test_hash_and_verify_ok():
    password_hash = hash_password("s3cret-password")
    assert password_hash != "s3cret-password"
    assert verify_password("s3cret-password", password_hash)


def test_verify_wrong_password():
    password_hash = hash_password("s3cret-password")
    assert not verify_password("wrong-password", password_hash)


def test_hash_is_salted():
    """Один и тот же пароль даёт разные хеши (соль bcrypt)."""
    assert hash_password("same") != hash_password("same")


def test_verify_invalid_hash_returns_false():
    """Битый хеш не должен бросать исключение."""
    assert not verify_password("any", "not-a-bcrypt-hash")
