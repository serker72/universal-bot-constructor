"""Хеширование паролей (bcrypt).

bcrypt — CPU-bound (~200 мс): из async-кода вызывать только async-обёртки
(`hash_password_async`, `verify_password_async`) — они выполняются в пуле
потоков и не блокируют event loop единственного воркера uvicorn.
"""

import asyncio

import bcrypt

# bcrypt использует только первые 72 байта пароля — длиннее задавать бессмысленно
MAX_PASSWORD_BYTES = 72
# Минимальная длина (символы): рекомендация — не короче 10 символов
MIN_PASSWORD_LENGTH = 10

# Распространённые пароли (топ утечек), недопустимые независимо от длины
COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "123456789a",
        "0987654321",
        "1q2w3e4r5t",
        "1qaz2wsx3edc",
        "qwertyuiop",
        "qwerty1234",
        "qwerty12345",
        "password12",
        "password123",
        "password1234",
        "passw0rd123",
        "iloveyou12",
        "adminadmin",
        "admin12345",
        "administrator",
        "welcome123",
        "letmein123",
        "1111111111",
        "0000000000",
        "aaaaaaaaaa",
        "abcdefghij",
        "abc1234567",
        "йцукенгшщз",
    }
)

# Хеш-заглушка для проверки пароля несуществующего пользователя: время ответа
# логина не должно зависеть от существования username (перечисление)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode()


class PasswordError(ValueError):
    """Пароль не проходит политику (длина, распространённый пароль)."""


def validate_password_policy(password: str) -> None:
    """Политика пароля: 10+ символов, ≤ 72 байт (bcrypt), не из списка частых."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordError(
            f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PasswordError(
            "Пароль должен быть не длиннее 72 байт "
            "(кириллический символ занимает 2 байта)"
        )
    if password.lower() in COMMON_PASSWORDS:
        raise PasswordError("Пароль слишком распространён — выберите другой")


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


async def hash_password_async(password: str) -> str:
    """hash_password в пуле потоков (не блокирует event loop)."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    """verify_password в пуле потоков.

    password_hash=None (пользователь не найден) — проверка против хеша-заглушки
    с тем же временем выполнения, результат всегда False.
    """
    if password_hash is None:
        await asyncio.to_thread(verify_password, password, _DUMMY_HASH)
        return False
    return await asyncio.to_thread(verify_password, password, password_hash)
