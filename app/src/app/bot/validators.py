"""Проверки телефона."""

import re

PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def normalize_phone(raw: str) -> str | None:
    """Нормализовать телефон (только цифры и ведущий +) или None."""
    phone = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not PHONE_RE.match(phone):
        return None
    return phone
