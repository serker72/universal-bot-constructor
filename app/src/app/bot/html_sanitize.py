"""Санитизация HTML краткого описания объекта для Telegram.

Описание объекта пишется пользователем как HTML-разметка. Telegram
поддерживает ограниченный набор тегов (документация Bot API,
«Formatting options», HTML style); недопустимые теги приводят к ошибке
400 «can't parse entities». Санитизация — библиотека ``nh3`` (Rust
``ammonia``, поддерживаемый преемник ``bleach``): whitelist тегов
Telegram, недопустимое вырезается, текст и допустимая разметка
сохраняются.
"""

import nh3

# теги Telegram (HTML style) и их допустимые атрибуты
_TAGS: dict[str, set[str]] = {
    "b": set(),
    "strong": set(),
    "i": set(),
    "em": set(),
    "u": set(),
    "ins": set(),
    "s": set(),
    "strike": set(),
    "del": set(),
    "code": {"class"},
    "pre": {"class"},
    "a": {"href", "class"},
    "blockquote": {"expandable"},
    "tg-spoiler": set(),
    # единственный «пустой» тег, поддерживаемый Telegram
    "br": set(),
}


def sanitize_html(value: str) -> str:
    """Допустимая HTML-разметка Telegram; недопустимые теги вырезаются."""
    return nh3.clean(
        value,
        tags=frozenset(_TAGS),
        attributes={tag: attrs for tag, attrs in _TAGS.items() if attrs},
        # Telegram не использует rel у ссылок
        link_rel=None,
    )
