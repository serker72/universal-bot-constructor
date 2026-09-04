"""Фикстуры unit-тестов.

Settings собирается с тестовыми переменными окружения, чтобы тесты
не зависели от содержимого .env (pdf-каталог — во tmp_path).
"""

import os

# Интеграционные тесты (tests/integration) подключаются к postgres напрямую,
# минуя pgbouncer: asyncpg кэширует prepared statements, что несовместимо
# с pool_mode=transaction у pgbouncer. Задаётся до первого импорта
# app.config.settings (глобальный settings читает env при импорте).
# Для unit-тестов значение не важно — они не подключаются к БД.
os.environ["POSTGRES_HOST"] = "postgres"
os.environ["SQLALCHEMY_DEBUG"] = "False"

import pytest

from app.config.settings import Settings


def pytest_collection_modifyitems(items):
    """Автоматическая разметка: tests/unit -> unit, tests/integration -> integration."""
    for item in items:
        path = str(item.fspath)
        if f"{os.sep}integration{os.sep}" in path:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Настройки приложения для unit-тестов."""
    monkeypatch.setenv("BACKEND_JWT_SECRET", "unit-test-secret-0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("BACKEND_PDF_DATA_DIR", str(tmp_path / "pdf"))
    monkeypatch.setenv("BACKEND_MAX_PDF_SIZE_MB", "1")
    return Settings()
