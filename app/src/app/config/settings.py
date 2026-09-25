"""Модуль конфигурации приложения.

Единый класс Settings агрегирует отдельные классы конфигурации,
разделённые по префиксам имён переменных окружения.

Подклассы читают переменные из os.environ (по своим префиксам).
Файл .env загружается один раз через python-dotenv:
- при локальной разработке — из корня проекта;
- в контейнере переменные уже в окружении (env_file в compose),
  load_dotenv просто ничего не делает.
"""

import re
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Секрет webhook (setWebhook.secret_token): 1–256 символов A-Z, a-z, 0-9, _ и -
WEBHOOK_SECRET_RE = re.compile(r"[A-Za-z0-9_-]{1,256}")

def _q(value: str) -> str:
    """URL-экранирование части DSN (пароль с / + @ : не ломает разбор URL)."""
    return quote(value, safe="")


# Корень проекта: app/src/app/config/settings.py -> parents[4]
PROJECT_ROOT = Path(__file__).resolve().parents[4]

# Загружаем .env из корня проекта в os.environ (если файл существует).
# В контейнере файл может отсутствовать — переменные уже заданы окружением.
load_dotenv(PROJECT_ROOT / ".env", override=False)


# ---------------------------------------------------------------------------
# Общие параметры проекта (префикс PROJECT_)
# ---------------------------------------------------------------------------
class ProjectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROJECT_",
        extra="ignore",
    )

    # loc / prod (выбирает docker-compose.nginx.{loc|prod}.yml); опечатка — ошибка старта
    environment: Literal["loc", "prod"] = "loc"
    url_scheme: str = "http"          # http / https
    domain: str = "localhost"


# ---------------------------------------------------------------------------
# PostgreSQL (префикс POSTGRES_)
# ---------------------------------------------------------------------------
class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        extra="ignore",
    )

    host: str = "pgbouncer"
    port: int = 5432
    db: str = "universal_bot_constructor"
    user: str = "universal_bot_constructor"
    password: str = ""

    # Тестовая БД
    test_db: str = "universal_bot_constructor_test"
    test_user: str = "universal_bot_constructor_test"
    test_password: str = ""

    @property
    def url(self) -> str:
        """DSN для SQLAlchemy (asyncpg); учётные данные URL-экранируются."""
        return (
            f"postgresql+asyncpg://{_q(self.user)}:{_q(self.password)}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def test_url(self) -> str:
        """DSN для тестовой БД."""
        return (
            f"postgresql+asyncpg://{_q(self.test_user)}:{_q(self.test_password)}"
            f"@{self.host}:{self.port}/{self.test_db}"
        )


# ---------------------------------------------------------------------------
# SQLAlchemy (префикс SQLALCHEMY_)
# ---------------------------------------------------------------------------
class SqlalchemySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SQLALCHEMY_",
        extra="ignore",
    )

    debug: bool = False
    # Пул поверх pgbouncer (pool_mode=transaction): ограниченный overflow —
    # без него (-1) число клиентских соединений не ограничено
    pool_size: int = 20
    max_overflow: int = 10
    pool_recycle: int = 600
    pool_use_lifo: bool = False
    pool_pre_ping: bool = True


# ---------------------------------------------------------------------------
# Redis (префикс REDIS_)
# ---------------------------------------------------------------------------
class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore",
    )

    host: str = "redis"
    port: int = 6379
    db: int = 0
    username: str | None = None
    password: str = ""

    @property
    def url(self) -> str:
        """DSN для redis-py / aiogram (username — ACL Redis 6+, опционально)."""
        if self.password:
            auth = f"{_q(self.username or '')}:{_q(self.password)}@"
        elif self.username:
            auth = f"{_q(self.username)}@"
        else:
            auth = ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


# ---------------------------------------------------------------------------
# RabbitMQ (префикс RABBITMQ_)
# ---------------------------------------------------------------------------
class RabbitmqSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_",
        extra="ignore",
    )

    host: str = "rabbitmq"
    port: int = 5672
    management_port: int = 15672
    # guest/guest — только для разработки; в prod — fail-fast (см. Settings)
    username: str = "guest"
    password: str = "guest"
    vhost: str = "/"

    @property
    def url(self) -> str:
        """AMQP DSN для faststream (vhost "/" кодируется как %2F)."""
        return (
            f"amqp://{_q(self.username)}:{_q(self.password)}"
            f"@{self.host}:{self.port}/{_q(self.vhost)}"
        )


# ---------------------------------------------------------------------------
# Backend / FastAPI (префикс BACKEND_)
# ---------------------------------------------------------------------------
class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BACKEND_",
        extra="ignore",
    )

    debug: bool = False
    worker_count: int = 2
    container_command: str = ""
    port: int = 8000
    api_prefix: str = "/api/v1"
    base_url: str = "http://localhost"

    # JWT (access+refresh в httpOnly cookies)
    jwt_secret: str = ""                 # BACKEND_JWT_SECRET (обязателен, см. Settings)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    # None — выводится из PROJECT_URL_SCHEME (https → True); явное значение переопределяет
    cookie_secure: bool | None = None
    cookie_domain: str | None = None     # домен для cookies (prod)

    # Загрузка PDF
    max_pdf_size_mb: int = 20

    # Каталог хранения PDF-файлов (BACKEND_PDF_DATA_DIR)
    pdf_data_dir: Path = Path("/data/universal-bot-constructor/pdf")


# ---------------------------------------------------------------------------
# Consumer / faststream (префикс CONSUMER_)
# ---------------------------------------------------------------------------
class ConsumerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONSUMER_",
        extra="ignore",
    )

    # Exchange уведомлений (direct): издатель публикует в него по routing key,
    # очереди привязываются к нему теми же ключами (имя очереди и routing
    # key независимы)
    exchange: str = "bot.notify"

    # Имена очередей уведомлений (консьюмеры бота, см. app.bot.notifications)
    queue_registration: str = "bot.notify.registration"
    queue_request_created: str = "bot.notify.request.created"
    queue_request_cancelled: str = "bot.notify.request.cancelled"
    queue_request_status: str = "bot.notify.request.status"

    # Routing keys: издатель и привязка очередей используют одни и те же значения
    routing_registration: str = "bot.notify.registration"
    routing_request_created: str = "bot.notify.request.created"
    routing_request_cancelled: str = "bot.notify.request.cancelled"
    routing_request_status: str = "bot.notify.request.status"


# ---------------------------------------------------------------------------
# Bot / aiogram (префикс BOT_)
# ---------------------------------------------------------------------------
class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOT_",
        extra="ignore",
    )

    token: str = ""
    proxy_url: str | None = None        # BOT_PROXY_URL — для AioHTTP-сессии

    # Webhook (prod): если webhook_base_url пуст — long-polling (dev/loc)
    webhook_base_url: str = ""          # BOT_WEBHOOK_BASE_URL, напр. https://example.com
    webhook_path: str = "/bot/webhook"  # путь на nginx и в set_webhook
    webhook_secret: str = ""            # BOT_WEBHOOK_SECRET — X-Telegram-Bot-Api-Secret-Token
    webhook_host: str = "0.0.0.0"       # хост aiohttp-приложения webhook
    webhook_port: int = 8080            # порт aiohttp-приложения webhook


# ---------------------------------------------------------------------------
# CORS (префикс CORS_)
# ---------------------------------------------------------------------------
class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CORS_",
        extra="ignore",
    )

    origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )


# ---------------------------------------------------------------------------
# Единый класс-агрегатор
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """Единый класс конфигурации приложения.

    Каждое поле — отдельный подкласс конфигурации, читающий свой префикс из .env.
    Файл .env загружается в окружение один раз (load_dotenv в начале модуля).
    """

    model_config = SettingsConfigDict(extra="ignore")

    project: ProjectSettings = Field(default_factory=ProjectSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    sqlalchemy: SqlalchemySettings = Field(default_factory=SqlalchemySettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbitmq: RabbitmqSettings = Field(default_factory=RabbitmqSettings)
    backend: BackendSettings = Field(default_factory=BackendSettings)
    consumer: ConsumerSettings = Field(default_factory=ConsumerSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        """Fail-fast проверки секретов при старте приложения.

        - JWT-секрет обязателен (иначе токены подделываются);
        - в prod секрет не короче 32 байт;
        - cookie_secure по умолчанию следует url_scheme (https → True);
        - webhook бота: секрет — формат Bot API (1–256, A-Z a-z 0-9 _ -);
          в prod при заданном BOT_WEBHOOK_BASE_URL — обязателен (иначе
          поддельные апдейты на публичный /bot/webhook).
        """
        if not self.backend.jwt_secret:
            raise ValueError(
                "BACKEND_JWT_SECRET обязателен; сгенерируйте: "
                "openssl rand -base64 64 | tr -d '\n'"
            )
        if (
            self.project.environment == "prod"
            and len(self.backend.jwt_secret.encode("utf-8")) < 32
        ):
            raise ValueError("BACKEND_JWT_SECRET в prod должен быть >= 32 байт")
        if self.backend.cookie_secure is None:
            self.backend.cookie_secure = self.project.url_scheme == "https"

        if self.project.environment == "prod":
            # дефолты для разработки в prod недопустимы
            if self.rabbitmq.password in ("", "guest"):
                raise ValueError(
                    "RABBITMQ_PASSWORD в prod не может быть пустым или guest"
                )
            if any("localhost" in origin for origin in self.cors.origins):
                raise ValueError(
                    "CORS_ORIGINS в prod не должен содержать localhost"
                )

        secret = self.bot.webhook_secret
        if secret and not WEBHOOK_SECRET_RE.fullmatch(secret):
            raise ValueError(
                "BOT_WEBHOOK_SECRET: 1–256 символов A-Z a-z 0-9 _ - "
                "(требование Telegram Bot API); сгенерируйте: openssl rand -hex 32"
            )
        if (
            self.project.environment == "prod"
            and self.bot.webhook_base_url
            and not secret
        ):
            raise ValueError(
                "BOT_WEBHOOK_SECRET обязателен в prod при заданном "
                "BOT_WEBHOOK_BASE_URL; сгенерируйте: openssl rand -hex 32"
            )
        return self


# Глобальный экземпляр для импорта в других модулях
settings = Settings()
