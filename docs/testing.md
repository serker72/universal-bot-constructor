# Тестирование

> Как устроены тесты, как их запускать и текущее покрытие.
> Обновлено: 2026-09-04 (172 теста, покрытие 66%).

---

## 1. Структура

```
app/
├── tests/
│   ├── conftest.py              # общие фикстуры + авто-разметка маркерами
│   ├── unit/                    # быстрые тесты без внешних зависимостей
│   │   ├── test_tokens.py       #   JWT (создание, разбор, TTL)
│   │   ├── test_security.py     #   TokenBlacklist, RateLimiter ( fakeredis )
│   │   ├── test_password.py     #   hash/verify (bcrypt)
│   │   ├── test_pdf.py          #   PdfService (валидация, сохранение, tmp_path)
│   │   ├── test_app_settings.py #   AppSettingsService
│   │   ├── test_schemas.py      #   pydantic-схемы API
│   │   └── test_validators.py   #   валидаторы бота
│   └── integration/             # реальные postgres + redis (тестовый контур)
│       ├── conftest.py          # фикстуры: engine, db, admin/manager-клиенты, данные
│       ├── test_auth_service.py #   AuthService (login/refresh/logout/отзыв)
│       ├── test_repositories.py #   репозитории
│       ├── test_api_auth.py     #   /auth/*
│       ├── test_api_users.py    #   /users/*
│       ├── test_api_categories.py   # /categories/*
│       ├── test_api_objects.py  #   /objects/* (+ менеджеры объекта)
│       ├── test_api_pdf.py      #   /objects/{id}/pdf
│       ├── test_api_sessions.py #   /sessions/*
│       ├── test_api_devices.py  #   /devices/*
│       ├── test_api_visitors.py #   /visitors/*
│       ├── test_api_requests.py #   /requests/*
│       └── test_api_settings.py #   /settings/*
├── Dockerfile.test              # образ test-runner (prod + dev-зависимости + tests)
docker-compose.test.yml          # тестовый контур (backend-test, bot-test, test-runner, ...)
```

Маркеры (проставляются автоматически по каталогу в `tests/conftest.py`):

- `unit` — без БД/redis/rabbitmq;
- `integration` — тестовая БД postgres, redis DB=1.

`pyproject.toml` ([tool.pytest.ini_options]): `asyncio_mode = "auto"`,
один event loop на сессию (`asyncio_default_fixture_loop_scope = "session"`),
т.к. интеграционные тесты используют общий движок SQLAlchemy и DI-контейнер.

## 2. Тестовый контур

Инфраструктура общая с продом (postgres, pgbouncer, redis, rabbitmq):
`docker compose -f docker-compose.srv.yml up -d`.

Тестовые приложения — из `docker-compose.test.yml`, **обязательно** с
`--env-file .env.test` (иначе compose возьмёт переменные из `.env`):

```bash
# сборка тестового образа (НУЖНА после любых правок src/ или tests/ —
# код запекается в образ, не монтируется!)
docker compose --env-file .env.test -f docker-compose.test.yml build test-runner

# миграции на тестовую БД
docker compose --env-file .env.test -f docker-compose.test.yml run --rm db-update-test

# тестовый контур (backend-test, bot-test, frontend-test, test-runner)
docker compose --env-file .env.test -f docker-compose.test.yml up -d

# остановить
docker compose --env-file .env.test -f docker-compose.test.yml down
```

## 3. Запуск тестов

`test-runner` держит контейнер живым (`tail -f /dev/null`), тесты запускаются
через `docker exec`:

```bash
# все тесты
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests -q

# только unit / только integration
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/unit -q
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/integration -q

# один файл / один тест
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/integration/test_api_sessions.py -q
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests/integration/test_api_auth.py::test_login_wrong_password_401 -q

# SQLAlchemy-предупреждения как ошибки (поймать cartesian product и т.п.)
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests -q -W "error::sqlalchemy.exc.SAWarning"
```

Время полного прогона: ~1:45 (integration ~1:30, unit ~2 с).

### Покрытие

```bash
docker exec ubc-test-runner /app/.venv/bin/python -m coverage run --source=src -m pytest tests -q
docker exec ubc-test-runner /app/.venv/bin/python -m coverage report
# HTML-отчёт: coverage html -> htmlcov/index.xml (внутри контейнера)
```

## 4. Покрытие (2026-09-04)

**Итого: 66%** (2057 statements, 694 miss). Тестов: 172 (65 unit + 107 integration).

| Модуль | Покрытие | Примечание |
|---|---|---|
| `api/schemas/` | 100% | |
| `domain/` | 100% | |
| `repository/` | 90%+ | `object` 59%, `request` 73%, `visitor` 84% |
| `services/` | 89–100% | `auth` 94%, `events` 89% |
| `config/settings.py` | 99% | |
| `api/deps.py` | 88% | |
| `api/main.py`, `health.py` | 83–89% | |
| `api/routers/` | 40–94% | `pdf` 40%, `requests` 49%, `objects` 53%, `visitors` 57%, `categories` 62%, `users` 65% |
| `bot/` | 0–28% | хендлеры, клавиатуры, main, states не покрыты |

### Зоны роста (по приоритету)

1. **`bot/`** (~450 строк) — хендлеры aiogram, клавиатуры, FSM. Нужны тесты
   с `MockBot`/фикстурами aiogram или интеграционные с фейковым Telegram API.
2. **`api/routers/objects.py` (53%)** — patch/delete, ветки pdf-обработки,
   часть `set_managers`.
3. **`api/routers/pdf.py` (40%)** — негативные сценарии: невалидный файл,
   превышение размера, отсутствие PDF при скачивании.
4. **`api/routers/requests.py` (49%)** — фильтры списка (status, date),
   доступ manager/admin, цепочки переходов статусов.

## 5. Известные особенности и грабли

- **Образ test-runner нужно пересобирать** после правок `src/` или `tests/` —
  код копируется в образ (см. `app/Dockerfile.test`), volume-монтирования нет.
  Симптом устаревшего образа: тесты падают на коде, которого уже нет в репо.
- **Cookies admin/manager в тестах**: `admin_client` и `manager_client` —
  *независимые* `AsyncClient` (см. `tests/integration/conftest.py`). Ранее оба
  строились на общем `client`, и второй login перезаписывал cookies — admin
  «становился» менеджером (403 на admin-эндпоинтах).
- **pgbouncer vs asyncpg**: интеграционные тесты подключаются к postgres
  напрямую (`POSTGRES_HOST=postgres` в `tests/conftest.py`, задаётся до импорта
  `app.config.settings`) — asyncpg кэширует prepared statements, что
  несовместимо с `pool_mode=transaction` у pgbouncer.
- **Очистка после каждого теста** (autouse-фикстуры в integration/conftest):
  `TRUNCATE ... RESTART IDENTITY CASCADE` всех таблиц + `flushdb` redis.
- **RabbitMQ в тестах не нужен**: брокер стартует только в lifespan приложения.
- **device_id при login**: login создаёт запись в `devices` — в тестах списка
  устройств учитывать устройство, созданное самим `admin_client` (total = 2).
- **httpx 0.28**: `resp.headers.get_list(...)` (не `getlist` — он есть только
  у starlette `Response`).
- **MissingGreenlet при сериализации**: после flush с server `onupdate=func.now()`
  атрибуты (`updated_at`) истекают — перед `model_validate` нужен
  `await session.refresh(obj, attribute_names=[...])`.
- **`BaseRepository.find_one()` ищет `self.model`**: нельзя использовать для
  поиска связевых таблиц (был баг в `ObjectRepository.remove_manager` —
  cartesian product `objects × object_managers`). Для связей — явный `select()`.
- **FK-нарушения**: FastAPI не валидирует существование `category_id` —
  ловится `IntegrityError` → 400 (см. `create_object` в `objects.py`).
