"""Интеграционные тесты: реальные postgres (тестовая БД) и redis.

Запускаются в контейнере test-runner (сеть ubc-backend):

    docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/integration -q

Предварительно:
    docker compose --env-file .env.test -f docker-compose.test.yml run --rm db-update-test

Особенности:
- postgres используется напрямую (минуя pgbouncer), см. tests/conftest.py;
- таблицы тестовой БД очищаются (TRUNCATE) после каждого теста;
- redis DB очищается после каждого теста;
- rabbitmq не нужен: брокер стартует только в lifespan приложения.
"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config.settings import Settings
from app.db.engine import create_engine, create_session_factory
from app.domain import Base
from app.domain.models import (
    Category,
    Object,
    Request,
    User,
    UserRole,
    Visitor,
)
from app.services.password import hash_password

API = "/api/v1"

# --- данные (переиспользуются тестами через фикстуры) -----------------------

ADMIN_USERNAME = "admin"
MANAGER_USERNAME = "manager"
ADMIN_PASSWORD = "admin-pass-123"
MANAGER_PASSWORD = "manager-pass-123"

CATEGORY_DATA = {"name": "Test category", "sort_order": 1, "is_active": True}
OBJECT_DATA = {
    "name": "Test object",
    "short_description": "Short description",
    "sort_order": 1,
    "is_active": True,
}
VISITOR_DATA = {"telegram_id": 100100100, "full_name": "Иванов Иван Иванович"}
REQUEST_PHONE = "+79991234567"
REQUEST_COMMENT = "Прошу консультацию"
PDF_FILENAME = "document.pdf"
PDF_CONTENT = b"%PDF-1.4 test pdf content"


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Настройки приложения (тестовая БД, redis DB=1 из .env.test)."""
    return Settings()


@pytest.fixture(scope="session")
async def engine(settings: Settings) -> AsyncEngine:
    """Движок тестовой БД (один на сессию, в общем event loop)."""
    engine = create_engine(settings)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def db(session_factory) -> AsyncSession:
    """Сессия БД на один тест (commit вызывается тестом явно)."""
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
async def _cleanup_db(engine: AsyncEngine):
    """Очистка всех таблиц тестовой БД после каждого теста."""
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )


@pytest.fixture(autouse=True)
async def _cleanup_redis(settings: Settings):
    """Очистка redis DB после каждого теста."""
    yield
    redis = Redis.from_url(settings.redis.url)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


# --- учётные данные и пользователи ------------------------------------------


@pytest.fixture
def admin_credentials() -> dict:
    """Логин/пароль администратора (создаётся фикстурой admin_user)."""
    return {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}


@pytest.fixture
def manager_credentials() -> dict:
    """Логин/пароль менеджера (создаётся фикстурой manager_user)."""
    return {"username": MANAGER_USERNAME, "password": MANAGER_PASSWORD}


@pytest.fixture
def device_id() -> str:
    """Идентификатор устройства для login (thumbmarkjs)."""
    return "test-device-0001"


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def manager_user(db: AsyncSession) -> User:
    user = User(
        username=MANAGER_USERNAME,
        password_hash=hash_password(MANAGER_PASSWORD),
        role=UserRole.MANAGER,
    )
    db.add(user)
    await db.commit()
    return user


# --- данные меню (категория -> объект) --------------------------------------


@pytest.fixture
def category_data() -> dict:
    """Данные для создания категории через API."""
    return dict(CATEGORY_DATA)


@pytest.fixture
def object_data() -> dict:
    """Данные для создания объекта через API (category_id подставляет тест)."""
    return dict(OBJECT_DATA)


@pytest.fixture
async def category(db: AsyncSession) -> Category:
    """Категория в БД."""
    cat = Category(**CATEGORY_DATA)
    db.add(cat)
    await db.commit()
    return cat


@pytest.fixture
async def obj(db: AsyncSession, category: Category) -> Object:
    """Объект в БД (привязан к category)."""
    o = Object(category_id=category.id, **OBJECT_DATA)
    db.add(o)
    await db.commit()
    return o


# --- посетители и заявки -----------------------------------------------------


@pytest.fixture
def visitor_data() -> dict:
    """Данные посетителя."""
    return dict(VISITOR_DATA)


@pytest.fixture
async def visitor(db: AsyncSession) -> Visitor:
    """Посетитель в БД (согласие дано)."""
    v = Visitor(
        **VISITOR_DATA,
        consent_given=True,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(v)
    await db.commit()
    return v


@pytest.fixture
async def request_obj(db: AsyncSession, visitor: Visitor, obj: Object) -> Request:
    """Новая заявка посетителя на объект."""
    r = Request(
        visitor_id=visitor.id,
        object_id=obj.id,
        phone=REQUEST_PHONE,
        comment=REQUEST_COMMENT,
    )
    db.add(r)
    await db.commit()
    return r


# --- HTTP-клиенты (ASGI, без реального сервера) -----------------------------


@pytest.fixture(scope="session")
def app():
    """Приложение FastAPI (DI-контейнер внутри, без запуска lifespan)."""
    from app.api.main import create_app

    return create_app()


@pytest.fixture
async def client(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


async def _login(client: AsyncClient, credentials: dict, device_id: str) -> None:
    resp = await client.post(
        f"{API}/auth/login",
        json={**credentials, "device_id": device_id},
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture
async def admin_client(
    app, admin_user: User, admin_credentials: dict, device_id: str
) -> AsyncClient:
    """Независимый клиент, вошедший как admin."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await _login(client, admin_credentials, device_id)
        yield client


@pytest.fixture
async def manager_client(
    app, manager_user: User, manager_credentials: dict, device_id: str
) -> AsyncClient:
    """Независимый клиент, вошедший как manager (cookies не пересекаются с admin)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await _login(client, manager_credentials, device_id)
        yield client
