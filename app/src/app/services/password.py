"""Хеширование паролей (bcrypt)."""

import bcrypt

# bcrypt использует только первые 72 байта пароля — длиннее задавать бессмысленно
MAX_PASSWORD_BYTES = 72


class PasswordError(ValueError):
    """Пароль не проходит политику (длина)."""


def validate_password_policy(password: str) -> None:
    """Проверка политики пароля: 8–72 байта (иначе bcrypt обрежет молча)."""
    size = len(password.encode("utf-8"))
    if size < 8:
        raise PasswordError("Пароль должен быть не короче 8 символов")
    if size > MAX_PASSWORD_BYTES:
        raise PasswordError("Пароль должен быть не длиннее 72 байт")


def hash_password(password: str) -> str:
    """Хешировать пароль (с проверкой политики)."""
    validate_password_policy(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль против хеша."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
