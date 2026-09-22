"""Интеграционные тесты: реальные postgres (тестовая БД) и redis.

Запускаются в контейнере test-runner (сеть ubc-backend):

    docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/integration -q

Предварительно:
    docker compose --env-file .env.test -f docker-compose.test.yml run --rm db-update-test

Особенности:
- postgres используется напрямую (минуя pgbouncer), см. tests/conftest.py;
- таблицы тестовой БД очищаются (TRUNCATE) после каждого теста, с
  lock_timeout/statement_timeout — блокировка даёт ошибку теста, а не зависание;
- redis DB очищается после каждого теста;
- rabbitmq не нужен: брокер стартует только в lifespan приложения.
"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config.settings import Settings
from app.db.engine import create_engine, create_session_factory
from app.domain import Base
from app.domain.models import (
    Category,
    Object,
    Request,
    RequestAvailableField,
    RequestCategoryField,
    RequestField,
    RequestFieldType,
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
VISITOR_PHONE = "+79991234567"
REQUEST_PHONE = "+79991234567"

# Справочник полей и значения заявки (динамический конструктор)
FIELD_TEXT_DATA = {
    "code": "comment",
    "type": RequestFieldType.TEXT,
    "label": "Комментарий",
    "is_required_default": False,
    "meta_data": {"max_length": 500},
}
FIELD_TIME_DATA = {
    "code": "delivery_time",
    "type": RequestFieldType.TIME,
    "label": "Время доставки",
    "is_required_default": True,
    "meta_data": {"minute_step": 15},
}
FIELD_VALUE_TEXT = "Прошу консультацию"
FIELD_VALUE_TIME = "14:30"

PDF_FILENAME = "document.pdf"
PDF_CONTENT = b"%PDF-1.4 test pdf content"

# Таймауты очистки БД после теста (см. фикстуру _cleanup_db)
LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "30s"


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
    """Очистка всех таблиц тестовой БД после каждого теста.

    TRUNCATE берёт ACCESS EXCLUSIVE lock. Без таймаутов он ждёт вечно, если
    мешает незавершённая транзакция (ошибка в тесте после выхода из DI-скоупа)
    или параллельный прогон pytest на той же БД, — весь прогон «зависает».
    Таймауты превращают блокировку в понятную ошибку теста.
    """
    yield
    try:
        async with engine.begin() as conn:
            # SET LOCAL — в пределах этой транзакции очистки
            await conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
            await conn.execute(
                text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
            )
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(
                    text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
                )
    except DBAPIError as exc:
        raise RuntimeError(
            "Очистка тестовой БД не выполнена: TRUNCATE заблокирован "
            f"(истёк lock_timeout={LOCK_TIMEOUT} / statement_timeout="
            f"{STATEMENT_TIMEOUT}). Причины: параллельный прогон pytest на той "
            "же тестовой БД (убедись, что запущен один) или незавершённая "
            f"транзакция в пуле соединений. Ошибка БД: {exc.orig}"
        ) from exc


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
    """Посетитель в БД (согласие дано, телефон в профиле)."""
    v = Visitor(
        **VISITOR_DATA,
        phone=VISITOR_PHONE,
        consent_given=True,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(v)
    await db.commit()
    return v


# --- поля заявки (динамический конструктор) ------------------------------------


@pytest.fixture
async def field_text(db: AsyncSession) -> RequestAvailableField:
    """TEXT-поле справочника (комментарий)."""
    f = RequestAvailableField(**FIELD_TEXT_DATA)
    db.add(f)
    await db.commit()
    return f


@pytest.fixture
async def field_time(db: AsyncSession) -> RequestAvailableField:
    """TIME-поле справочника (время доставки, шаг минут 15)."""
    f = RequestAvailableField(**FIELD_TIME_DATA)
    db.add(f)
    await db.commit()
    return f


@pytest.fixture
async def category_with_fields(
    db: AsyncSession,
    category: Category,
    field_text: RequestAvailableField,
    field_time: RequestAvailableField,
) -> Category:
    """Категория с привязанными полями (comment → delivery_time)."""
    db.add(
        RequestCategoryField(
            category_id=category.id,
            field_id=field_text.id,
            sort_order=1,
            is_required=False,
        )
    )
    db.add(
        RequestCategoryField(
            category_id=category.id,
            field_id=field_time.id,
            sort_order=2,
            is_required=True,
        )
    )
    await db.commit()
    return category


@pytest.fixture
async def request_obj(
    db: AsyncSession,
    visitor: Visitor,
    obj: Object,
    field_text: RequestAvailableField,
    field_time: RequestAvailableField,
) -> Request:
    """Новая заявка посетителя на объект со значениями полей."""
    r = Request(
        visitor_id=visitor.id,
        object_id=obj.id,
        phone=REQUEST_PHONE,
    )
    db.add(r)
    await db.flush()
    db.add_all(
        [
            RequestField(
                request_id=r.id,
                field_id=field_text.id,
                value_text=FIELD_VALUE_TEXT,
            ),
            RequestField(
                request_id=r.id,
                field_id=field_time.id,
                value_text=FIELD_VALUE_TIME,
            ),
        ]
    )
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
