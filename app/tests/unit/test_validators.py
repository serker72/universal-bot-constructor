"""Тесты нормализации телефона (app.bot.validators)."""

import pytest

from app.bot.validators import normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+79991234567", "+79991234567"),
        ("+7 999 123-45-67", "+79991234567"),
        ("8(999)1234567", "89991234567"),
        ("89991234567", "89991234567"),
        ("79991234567", "79991234567"),
        ("  +79991234567  ", "+79991234567"),
        ("+7(999)123-45-67", "+79991234567"),
        ("+79991234567890", "+79991234567890"),  # 13 цифр — в допустимых 10..15
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "abc",
        "12345",           # слишком короткий
        "+799912345678901234",  # 16+ цифр — слишком длинный
        "телефон",
        "",
        "+7-999",          # после очистки слишком короткий
    ],
)
def test_normalize_phone_invalid(raw):
    assert normalize_phone(raw) is None
