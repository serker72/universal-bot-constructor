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
    monkeypatch.setenv("RABBITMQ_PASSWORD", "unit-test-rabbit-password")
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.org"]')


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


def test_prod_rejects_guest_rabbitmq_password(monkeypatch):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "prod")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "guest")
    with pytest.raises(ValidationError, match="RABBITMQ_PASSWORD"):
        Settings()


def test_prod_rejects_localhost_cors(monkeypatch):
    monkeypatch.setenv("PROJECT_ENVIRONMENT", "prod")
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings()


def test_dsn_credentials_are_url_quoted(monkeypatch):
    """Пароли с / + @ : не ломают DSN; REDIS_USERNAME попадает в URL."""
    from sqlalchemy.engine import make_url

    password = "p@ss/w:rd+1"
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    monkeypatch.setenv("REDIS_PASSWORD", password)
    monkeypatch.setenv("REDIS_USERNAME", "ubc")
    monkeypatch.setenv("RABBITMQ_PASSWORD", password)
    monkeypatch.setenv("RABBITMQ_VHOST", "/")
    settings = Settings()
    assert make_url(settings.postgres.url).password == password
    assert settings.redis.url.startswith("redis://ubc:p%40ss%2Fw%3Ard%2B1@")
    assert settings.rabbitmq.url.endswith("/%2F")
