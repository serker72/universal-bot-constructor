"""Модуль конфигурации приложения.

Единый класс Settings агрегирует отдельные классы конфигурации,
разделённые по префиксам имён переменных окружения.

Подклассы читают переменные из os.environ (по своим префиксам).
Файл .env загружается один раз через python-dotenv:
- при локальной разработке — из корня проекта;
- в контейнере переменные уже в окружении (env_file в compose),
  load_dotenv просто ничего не делает.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    environment: str = "loc"          # loc / dev / prod
    url_scheme: str = "http"          # http / https
    domain: str = "localhost"
    data_dir: Path = Path("/data/universal-bot-constructor")


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
    data_dir: Path = Path("/data/universal-bot-constructor/db")
    backups_dir: Path = Path("/data/universal-bot-constructor/backups")

    # Тестовая БД
    test_db: str = "universal_bot_constructor_test"
    test_user: str = "universal_bot_constructor_test"
    test_password: str = ""

    @property
    def url(self) -> str:
        """DSN для SQLAlchemy (asyncpg)."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def test_url(self) -> str:
        """DSN для тестовой БД."""
        return (
            f"postgresql+asyncpg://{self.test_user}:{self.test_password}"
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
    pool_size: int = 50
    max_overflow: int = -1
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
    data_dir: Path = Path("/data/universal-bot-constructor/redis")

    @property
    def url(self) -> str:
        """DSN для redis-py / aiogram."""
        auth = f":{self.password}@" if self.password else ""
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
    username: str = "guest"
    password: str = "guest"
    vhost: str = "/"
    data_dir: Path = Path("/data/universal-bot-constructor/rabbitmq")

    @property
    def url(self) -> str:
        """AMQP DSN для faststream."""
        return (
            f"amqp://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.vhost}"
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
    jwt_secret: str = ""                 # BACKEND_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    cookie_secure: bool = False          # True — только по HTTPS (prod)
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

    # Имена очередей уведомлений (консьюмеры бота, см. app.bot.notifications)
    queue_registration: str = "bot.notify.registration"
    queue_request_created: str = "bot.notify.request.created"
    queue_request_cancelled: str = "bot.notify.request.cancelled"
    queue_request_status: str = "bot.notify.request.status"

    # Routing keys издателя (должны совпадать с привязкой очередей!)
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
# Frontend / Nuxt.js (префикс FRONTEND_)
# ---------------------------------------------------------------------------
class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRONTEND_",
        extra="ignore",
    )

    port: int = 3000
    host: str = "0.0.0.0"


# ---------------------------------------------------------------------------
# Nginx (префикс NGINX_)
# ---------------------------------------------------------------------------
class NginxSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NGINX_",
        extra="ignore",
    )

    port: int = 80
    ssl_port: int = 443


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
    frontend: FrontendSettings = Field(default_factory=FrontendSettings)
    nginx: NginxSettings = Field(default_factory=NginxSettings)


# Глобальный экземпляр для импорта в других модулях
settings = Settings()
