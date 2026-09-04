"""Настройка логирования: logging + structlog.

- debug (локальная разработка) — консольный вывод, удобный для чтения;
- иначе — JSON (для сбора логов в prod).
"""

import logging
import sys

import structlog


def setup_logging(debug: bool = False) -> None:
    """Настроить stdlib logging и structlog (один раз при старте процесса)."""
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(message)s",
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: list = (
        [structlog.dev.ConsoleRenderer()]
        if debug
        else [structlog.processors.JSONRenderer()]
    )

    structlog.configure(
        processors=[*shared_processors, *renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Приглушить шумные логи библиотек в prod
    if not debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None):
    """Получить structlog-логгер."""
    return structlog.get_logger(name)
