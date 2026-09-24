"""Тесты fail-fast валидации Settings (окружение, секрет webhook бота)."""

import pytest
from pydantic import ValidationError

from app.config.settings import Settings

VALID_SECRET = "a1B2_c3-" * 8  # 64 символа из допустимого набора


@pytest.fixture(autouse=True)
def _base_env(monkeypatch, tmp_path):
    """Минимальное окружение: JWT-секрет (>= 32 байт), без webhook."""
    monkeypatch.setenv("BACKEND_JWT_SECRET", "unit-test-secret-0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("BACKEND_PDF_DATA_DIR", str(tmp_path / "pdf"))
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "loc")
    monkeypatch.setenv("BOT_WEBHOOK_BASE_URL", "")
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", "")


@pytest.mark.parametrize("env", ["loc", "prod"])
def test_environment_allowed(monkeypatch, env):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", env)
    assert Settings().project.environment == env


@pytest.mark.parametrize("env", ["dev", "production", "Prod", ""])
def test_environment_rejected(monkeypatch, env):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", env)
    with pytest.raises(ValidationError):
        Settings()


def test_prod_webhook_requires_secret(monkeypatch):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "prod")
    monkeypatch.setenv("BOT_WEBHOOK_BASE_URL", "https://example.org")
    with pytest.raises(ValidationError, match="BOT_WEBHOOK_SECRET обязателен"):
        Settings()


def test_prod_webhook_with_secret_ok(monkeypatch):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "prod")
    monkeypatch.setenv("BOT_WEBHOOK_BASE_URL", "https://example.org")
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", VALID_SECRET)
    assert Settings().bot.webhook_secret == VALID_SECRET


def test_prod_polling_without_secret_ok(monkeypatch):
    """Без BOT_WEBHOOK_BASE_URL бот работает в long-polling — секрет не нужен."""
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "prod")
    assert Settings().bot.webhook_secret == ""


def test_loc_webhook_without_secret_ok(monkeypatch):
    monkeypatch.setenv("BOT_WEBHOOK_BASE_URL", "https://example.org")
    assert Settings().bot.webhook_base_url == "https://example.org"


@pytest.mark.parametrize(
    "secret",
    [
        "abc+def",          # base64-символы недопустимы
        "abc/def=",
        "секрет",           # не ASCII
        "with space",
        "x" * 257,          # длиннее 256
    ],
)
def test_webhook_secret_format_rejected(monkeypatch, secret):
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", secret)
    with pytest.raises(ValidationError, match="BOT_WEBHOOK_SECRET"):
        Settings()


@pytest.mark.parametrize("secret", ["a", "A-z_09", "f" * 64, "x" * 256])
def test_webhook_secret_format_ok(monkeypatch, secret):
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", secret)
    assert Settings().bot.webhook_secret == secret
