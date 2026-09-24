# Архитектура системы «Универсальный конструктор меню бота Telegram»

> Итоговый документ проектирования (шаг 8). План разработки — `docs/design-plan.md`.

---

## 1. Обзор

Приложение управляет двухуровневым меню Telegram-бота: **категории → объекты**
(объект: категория, наименование, краткое описание HTML, PDF с полным
описанием). Контент и пользователи управляются через веб-админку; посетители
работают с ботом: регистрация (ФИО + согласие на обработку ПД), просмотр меню,
получение PDF, создание и отмена заявок (форма строится динамически по
настраиваемым полям категории). Менеджеры обрабатывают заявки по своим
объектам в админке.

### Роли

| Роль | Где | Права |
|---|---|---|
| **admin** | frontend | пользователи, настройки, справочник полей заявки, контент (категории/объекты, CRUD), просмотр всех заявок (без обработки), бан посетителей, сессии/устройства |
| **manager** | frontend | чтение своих категорий и объектов (прямая связь объект↔менеджер ∪ назначенные категории), обработка заявок по ним, дашборд |
| **visitor** | bot | регистрация, меню, PDF, заявки |

### Стек

- **services**: nginx, postgresql, pgbouncer, redis, rabbitmq (docker compose)
- **backend**: Python 3.13, uv, FastAPI, dishka, SQLAlchemy async, asyncpg,
  Alembic, faststream (RabbitMQ), structlog, PyJWT, bcrypt, nh3 (санитизация HTML)
- **bot**: aiogram 3 (FSM в Redis), aiogram-dialog (динамическая форма заявки),
  aiohttp-сессия (SOCKS-прокси опционально)
- **frontend**: Nuxt 3 (SPA), TailwindCSS, thumbmarkjs
- **контейнеры**: docker compose (`docker-compose.yml` включает
  `docker-compose.srv.yml` + `docker-compose.backend.yml` +
  `docker-compose.frontend.yml`)

---

## 2. Компоненты и сети

```
                       ┌──────────────────────────── docker-сеть ubc-frontend ───────────────────────────┐
 браузер ──► nginx :80 │ ── /api/  ─► backend:8000 (FastAPI)                                             │
 (админка, SPA)        │ ── /bot/   ─► bot:8080 (webhook, prod)                                          │
                       │ ── /       ─► frontend:3000 (Nuxt SPA)                                          │
                       └─────────────────────────────────────────────────────────────────────────────────┘
                       ┌──────────────────────────── docker-сеть ubc-backend ────────────────────────────┐
 backend ◄─ pgbouncer ─┤─► postgresql        backend/bot ─► redis (сессии, FSM, blacklist, rate-limit)
 backend ─┐            │
 bot ─────┴─► rabbitmq ┤ (события уведомлений)      bot ─► api.telegram.org (long-polling / webhook)
                       └─────────────────────────────────────────────────────────────────────────────────┘
```

- **nginx** (`srv/nginx/`) — reverse proxy: `/api/` → backend, `/bot/` → bot
  (webhook в prod), `/` → frontend; `client_max_body_size 25m` (загрузка PDF).
- **Общий volume** `${BACKEND_PDF_DATA_DIR}` смонтирован в backend **и** bot —
  PDF, загруженный через админку, отправляется ботом как документ Telegram.
- **RabbitMQ** — единственный канал связи backend/bot → bot для уведомлений
  (издатель и консьюмеры используют одинаковые routing keys из `.env`).

### Слои backend (`app/src/app/`)

```
api/routers/        FastAPI-роутеры (DishkaRoute, FromDishka), схемы api/schemas/
services/           бизнес-логика: auth, tokens, pdf, app_settings, events (издатель)
repository/         SQLAlchemy async-репозитории (базовый + по сущностям)
domain/models/      ORM-модели
di/                 провайдеры dishka: settings, db, redis, broker, repository, service, bot
config/settings.py  pydantic-settings (префиксы POSTGRES_/REDIS_/RABBITMQ_/BACKEND_/BOT_/CONSUMER_/CORS_)
bot/                aiogram: handlers/, keyboards.py (CallbackData), services.py,
                    notifications.py, dialogs/ (динамический диалог заявки),
                    widgets/ (RuCalendar), states.py (FSM-группы)
db/                 движок, фабрика сессий (commit при успехе / rollback при ошибке)
```

DI-скоупы dishka: **APP** (engine, redis, broker, Bot, EventPublisher, PdfService),
**REQUEST** (сессия БД, репозитории, AuthService, BotService). Сессия БД на запрос:
`commit` при успехе, `rollback` при исключении.

---

## 3. ER-модель

```
users ─┬─< object_managers >─ objects ─> categories ─┬─< category_managers >─ users
       │                                  │          │
       ├─< devices ─< sessions            │          └─< request_category_fields >─ request_available_fields
       │                                  │                        │
       │              requests >──────────┘                        │
       │                 │                                         │
       │                 └────────< request_fields >───────────────┘
       └─ (telegram_id) visitors ──< requests

settings (key/value, отдельная таблица)
```

| Таблица | Ключевые поля | Назначение |
|---|---|---|
| **users** | id, username (unique), password_hash (bcrypt), role (admin/manager), telegram_id (nullable), is_active | персонал админки; telegram_id — для уведомлений |
| **categories** | id, name, sort_order, is_active | уровень 1 меню |
| **objects** | id, category_id FK, name, short_description, pdf_path, sort_order, is_active | уровень 2 меню; pdf_path — относительный путь в PDF-каталоге |
| **object_managers** | id, object_id FK, user_id FK, unique(object_id, user_id) | какие менеджеры обслуживают объект (прямая связь) |
| **category_managers** | id, category_id FK, user_id FK, unique(category_id, user_id) | менеджер категории — доступ ко **всем** объектам категории; доступ к объекту = прямая связь ∪ связь категории |
| **visitors** | id, telegram_id (unique), full_name, phone (nullable), consent_given, consent_at, is_blocked, blocked_at | посетители бота; phone — телефон из профиля (для диалога заявки) |
| **requests** | id, visitor_id FK, object_id FK, phone, status (enum), confirmed_at (nullable) | заявки; статусы: `new → approved/rejected`, `approved → completed`, `new/approved → cancelled_by_customer`; остальные данные — динамические поля (`request_fields`) |
| **request_available_fields** | id, code (unique), type (enum `tp_request_field_type`: text/number/date/time/select), label, is_required_default, meta_data (JSONB, nullable) | справочник полей формы заявки; meta_data — параметры по типу: `{"options": [...]}` (SELECT), `{"minute_step": 15}` (TIME), `{"min","max"}` (NUMBER), `{"max_length": 500}` (TEXT) |
| **request_category_fields** | id, category_id FK (CASCADE), field_id FK (CASCADE), sort_order, is_required, unique(category_id, field_id) | состав и порядок полей формы заявки категории |
| **request_fields** | id, request_id FK (CASCADE), field_id FK (**RESTRICT**), value_text (String(1024), nullable), unique(request_id, field_id) | значения динамических полей конкретной заявки; RESTRICT сохраняет историю заявок |
| **devices** | id, user_id FK, device_id (thumbmarkjs), user_agent, last_seen_at | устройства входа |
| **sessions** | id, device_id FK, user_id FK, refresh_token_jti, is_active, revoked_at | refresh-сессии (ротация, отзыв) |
| **settings** | key (PK), value | page_size (10), cancel_interval_minutes (1440 = 24 ч), welcome_text, consent_text (тексты — HTML, санитизируются в боте) |

Миграции: `app/alembic/versions/` (18 миграций, async-движок). Запуск — см. §7.

---

## 4. API-контракты (FastAPI, префикс `/api/v1`)

Авторизация: JWT **access + refresh в httpOnly cookies** (`ubc_access`,
`ubc_refresh`). Refresh хранит jti в таблице sessions; при logout/отзыве оба
токена заносятся в blacklist в Redis (TTL = остаток жизни токена). На каждое
устройство — своя сессия (device_id из thumbmarkjs).

| Метод и путь | Роль | Назначение |
|---|---|---|
| `POST /auth/login` | — | вход (rate-limit по IP), ставит cookies, создаёт сессию+device |
| `POST /auth/refresh` | cookie | ротация refresh (старый jti деактивируется) |
| `POST /auth/logout` | cookie | blacklist обоих токенов, деактивация сессии |
| `GET/POST/PATCH/DELETE /categories[/{id}]` | admin (GET — также manager: только доступные) | CRUD категорий (+sort_order, is_active, button_text — текст кнопки «Создать заявку»; PATCH: null — не менять, "" — дефолт) |
| `GET/PUT /categories/{id}/managers` | admin | менеджеры категории (доступ ко всем объектам категории) |
| `GET/POST/PATCH/DELETE /objects[/{id}]` | admin (GET — также manager: только доступные) | CRUD объектов |
| `GET/PUT /objects/{id}/managers` | admin | список менеджеров объекта (только **прямые** связи) |
| `PUT /objects/{id}/pdf` | admin | загрузка PDF (multipart, только application/pdf, ≤20 МБ) |
| `GET /objects/{id}/pdf` | auth | отдача PDF (inline, открытие в новой вкладке) |
| `GET/POST /request-fields`, `GET/PATCH/DELETE /request-fields/{id}` | admin | справочник полей заявки (валидация `meta_data` по типу; удаление со значениями заявок → 400, FK RESTRICT) |
| `GET/PUT /request-fields/categories/{id}/fields` | admin | состав полей формы заявки категории (PUT — полный список, diff) |
| `GET/POST/PATCH/DELETE /users[/{id}]` | admin | CRUD персонала (защита последнего admin, запрет самоудаления) |
| `GET /visitors`, `POST /visitors/{id}/block`, `/unblock` | admin | посетители: поиск/фильтры, бан/разбан |
| `GET /requests` | admin/manager | список; менеджер — только по своим объектам (прямые ∪ категории); фильтры статус/объект/дата (`created_at`); в `RequestOut.fields` — значения динамических полей |
| `GET /requests/{id}` | admin/manager | карточка заявки (тот же `RequestOut`) |
| `POST /requests/{id}/status` | manager объекта | переходы: new→approved/rejected, approved→completed; публикует событие для уведомления посетителя |
| `GET /devices` | admin | устройства, фильтр по пользователю |
| `GET /sessions`, `POST /sessions/{id}/revoke`, `POST /sessions/revoke-all` | admin | сессии и их отзыв |
| `GET/PUT /settings` | admin | только известные ключи (4 ключа, см. ER) |
| `GET /health`, `GET /health/ready` | — | liveness / readiness (SELECT 1) |

Ошибки — стандартный FastAPI `{"detail": "..."}`; 401/403 по ролям; frontend
при 401 автоматически делает refresh и повторяет запрос (`useApi`).

---

## 5. Бот (aiogram 3)

### Сценарии

- `/start`: незарегистрированный → flow **ФИО → телефон (валидация формата) →
  согласие** (текст из settings); заблокированный → сообщение о блокировке;
  зарегистрированный → главное меню.
- **Меню**: категории (пагинация page_size из settings) → объекты → карточка
  объекта (описание — HTML с санитизацией `nh3` по whitelist тегов Telegram,
  «Получить PDF» → документ Telegram, «Создать заявку» — текст кнопки из
  `categories.button_text`, дефолт «Создать заявку»).
- **Заявка (динамический диалог aiogram-dialog)**: состав шагов задаёт админ
  для категории объекта (`request_category_fields`). Порядок: телефон (из
  профиля `visitors.phone` или новый — текст/контакт, `normalize_phone`) →
  поля схемы по типу (`text`/`number` — `MessageInput`, `date` — `RuCalendar`,
  `time` — часы+минуты `Select`, `select` — опции из `meta_data`) → `summary`
  (проверка + «Отправить»). Состояния — по типу поля (`DynamicRequestSG`),
  динамичность обеспечивает routing engine: `process_and_go_next` (ответ →
  шаг +1 → переключение по типу следующего поля, конец схемы → `summary`),
  `go_back` (по `current_step - 1`), для TIME — `temp_hour` между окнами.
  Валидация по типам: TEXT — `max_length`, NUMBER — int/float + `min`/`max`,
  SELECT — значение из опций, «-»/«Пропустить» — только для необязательных;
  обязательные поля проверяются на `summary` (незаполненные → alert).
  Финализация — `BotService.create_request(visitor, object_id, phone, values)`:
  `Request` (status=new) + bulk `RequestField` одной транзакцией → уведомление
  менеджерам объекта. Пустая схема → сразу `summary`.
- **Мои заявки**: список с пагинацией, статусы, значения динамических полей
  (`label: value`), отмена: `new` — всегда, `approved` — в пределах
  `cancel_interval_minutes` от `confirmed_at` (момента подтверждения
  менеджером; дефолт 1440 мин = 24 ч).
- FSM хранится в Redis (`RedisStorage`, key builder с bot_id и destiny).

### Callback-схема

Только типизированные классы `CallbackData` (`bot/keyboards.py`):
`CategoryCB`, `ObjectCB`, `ObjectActionCB`, `CreateRequestCB`, `RequestCB`,
`ConsentCB`, `MenuCB`. Хендлеры получают зависимости через `FromDishka`;
инъекция включается `setup_dishka(container, dp, auto_inject=True)`
(без `auto_inject` хендлеры не оборачиваются → `TypeError` при апдейте).

### Уведомления (RabbitMQ, faststream)

Имена очередей и routing keys — в `.env` (`CONSUMER_QUEUE_*`,
`CONSUMER_ROUTING_*`), значения должны совпадать (default exchange,
привязка очереди по routing key). Расхождение → `Basic.Return` (сообщение
теряется молча).

| Событие (routing key) | Издатель | Получатель |
|---|---|---|
| `bot.notify.registration` | bot (регистрация посетителя) | все admin с telegram_id |
| `bot.notify.request.created` | bot (создание заявки) | менеджеры объекта (прямые + категория объекта) |
| `bot.notify.request.cancelled` | bot (отмена посетителем) | менеджеры объекта (прямые + категория объекта) |
| `bot.notify.request.status` | backend (смена статуса заявки) | посетитель заявки |

Особенности: telegram_id не указан → пропуск (не ошибка); ошибка отправки
одному получателю не прерывает рассылку (`notify_send_failed`).

**Порядок запуска бота критичен** (`bot/main.py`): получить `RabbitBroker` →
зарегистрировать `@broker.subscriber` → `await broker.start()`. В faststream 0.7
подписчики, добавленные **после** старта брокера, не создают очередей.

---

## 6. Потоки данных

### Вход в админку
```
браузер → thumbmarkjs (fingerprint → device_id)
        → POST /auth/login (login, password) → backend: bcrypt-проверка,
          rate-limit (Redis), JWT-пара (jti в sessions), device фиксируется
        → httpOnly cookies → SPA грузит данные
```

### Публикация контента
```
admin → frontend → POST/PATCH /categories, /objects → PostgreSQL
admin → PUT /objects/{id}/pdf (multipart) → PdfService: валидация (PDF, ≤20МБ)
        → файл в {BACKEND_PDF_DATA_DIR}/{object_id}/ → путь в objects.pdf_path
        (volume общий с ботом)
```

### Регистрация посетителя
```
бот /start → FSM: ФИО → телефон → согласие
        → visitors (telegram_id unique, consent_given/at)
        → publish bot.notify.registration → консьюмер бота → админам
```

### Заявка (полный цикл)
```
админ:   frontend /fields → справочник полей (code, type, label, meta_data)
         frontend /categories → «Поля заявки»: состав + sort_order + is_required
посетитель: бот «Создать заявку» → dialog_manager.start(input_phone,
            start_data={"schema": поля категории объекта, "answers": {}})
        → телефон из профиля/новый → шаги по типу поля → summary
        → requests (new, phone) + request_fields (request_id, field_id, value_text)
        → publish bot.notify.request.created → менеджерам объекта (прямо + категория)
менеджер:  frontend POST /requests/{id}/status (approved/rejected/completed)
        → БД → publish bot.notify.request.status → посетителю
посетитель: отмена (new всегда; approved в пределах cancel_interval_hours)
        → статус cancelled_by_customer → publish bot.notify.request.cancelled
        → менеджерам объекта (прямо + категория)
```

---

## 7. Запуск и эксплуатация

### Полный стек (docker)

```bash
cp .env.example .env          # заполнить секреты
docker compose up -d --build  # loc: 8 контейнеров (nginx, frontend, backend, bot,
                              # postgres, pgbouncer, redis, rabbitmq); prod: + certbot
```

Nginx подключается по окружению: `docker-compose.yml` → `include`
`docker-compose.nginx.${PROJECT_ENVIRONMENT:-loc}.yml` (без compose profiles):

| | loc | prod |
|---|---|---|
| шаблоны (`envsubst`) | `srv/nginx/templates/loc/default.conf.template` — :80, все location | `templates/prod/default.conf.template` — :80, ACME + 301 на https; `ssl.conf.template` — :443, TLS 1.2/1.3, HSTS 24 ч |
| SSL | не используется | Let's Encrypt (webroot HTTP-01), `${CERTBOT_DATA_DIR}/{conf,www}` |
| certbot | — | `certbot renew` каждые 12 ч |
| reload nginx | — | каждые 6 ч (`srv/nginx/docker-entrypoint.d/40-reload-certs.sh`) |

Общие фрагменты — `srv/nginx/snippets/` (`proxy_params.conf`,
`proxy_websocket_params.conf`). Nginx `depends_on` frontend/backend/bot
(upstream'ы резолвятся при старте). Первичный выпуск сертификата —
`./init-letsencrypt.sh` (временный самоподписанный → nginx → `certbot certonly`
→ reload; `--staging`, `--force`; staging-сертификат при запуске без
`--staging` заменяется боевым автоматически — `certbot delete` + выпуск).

Администратор: `docker compose run --rm backend python -m app.scripts.create_admin
--username admin [--password ...] [--role admin|manager]` (идемпотентно;
exit 0/1/2 — успех/неверный ввод/ошибка БД).

Миграции (локально, из корня):

```bash
PYTHONPATH=app/src POSTGRES_HOST=127.0.0.1 .venv/bin/alembic -c app/alembic.ini upgrade head
```

или через docker: `docker compose -f docker-compose.dbupdate.yml run --rm db-update`.

### Локальная разработка

- backend/bot — корневой `.venv` (`uvicorn src.app.api.main:app --reload`,
  `python -m src.app.bot.main`);
- frontend — `npm run dev` (проксирует на `NUXT_PUBLIC_BACKEND_URL`);
- инфраструктура — `docker compose -f docker-compose.srv.yml up -d`.

### Конфигурация

Все переменные — в `.env` (шаблон `.env.example`), читаются pydantic-settings
(`app/config/settings.py`): `PROJECT_*`, `POSTGRES_*`, `REDIS_*`,
`RABBITMQ_*`, `SQLALCHEMY_*`, `CORS_*`, `BACKEND_*` (включая `BACKEND_JWT_SECRET`,
`BACKEND_PDF_DATA_DIR`), `CONSUMER_*` (очереди/routing keys), `BOT_*`
(токен, прокси, webhook). Секреты в git не попадают.

### Логирование

structlog: console (dev) / JSON (prod), уровень — по `PROJECT_ENVIRONMENT`.
Ключевые события: `bot_started_polling`, `notify_send_failed`,
`notify_visitor_failed`; SQL-лог — по `SQLALCHEMY_DEBUG`.

### Известные особенности

- nginx кеширует IP контейнеров: после пересоздания backend/bot нужен
  `docker exec ubc-nginx nginx -s reload`;
- PDF открывается в новой вкладке с cookies — работает только на том же домене,
  что и админка (иначе httpOnly cookies не отправятся);
- `crypto.subtle` (thumbmarkjs) недоступен вне secure context — есть фолбэк
  FNV-1a-хеш для HTTP-разработки;
- **SQLAlchemy async + сериализация**: любые relationship, к которым обращается
  pydantic-схема, обязаны быть загружены eagerly (`selectinload`). Значения
  динамических полей отдаются как `value.field.code/label`, поэтому заявки
  читаются через `RequestRepository.get_with_values()` / `list_page` со связкой
  `selectinload(Request.values).selectinload(RequestField.field)`; ленивая
  загрузка даёт `MissingGreenlet` при сборке ответа;
- **`session.delete()` без flush**: ограничение FK (RESTRICT при удалении поля
  справочника со значениями) всплывает только на `commit`, когда HTTP-ответ
  уже сформирован. Такие места требуют явного `await session.flush()` внутри
  try/except `IntegrityError` (см. `DELETE /request-fields/{id}`);
- **тесты и незавершённые транзакции**: фикстура `_cleanup_db` делает
  `TRUNCATE ... RESTART IDENTITY CASCADE` (ACCESS EXCLUSIVE lock, `lock_timeout`
  не задан). Блокировка вечна, если мешает незавершённая транзакция — ошибка в
  тесте после выхода из DI-скоупа (сериализация ответа) оставляет открытую
  транзакцию в соединении пула — либо **второй прогон pytest** на той же тестовой
  БД. Защита: `pytest-timeout` (`timeout = 120` в `app/pyproject.toml`) прерывает
  висящий тест; правила — один прогон за раз, после обрыва `docker exec`
  проверять `docker top ubc-test-runner`; признаки блокировки — `pg_stat_activity`
  (`state`, `wait_event`, `xact_age`).

### Тесты

Запуск в docker (test-runner, тестовый контур `docker-compose.test.yml`):

```bash
docker compose --env-file .env.test -f docker-compose.test.yml build test-runner
docker compose --env-file .env.test -f docker-compose.test.yml up -d test-runner
docker compose --env-file .env.test -f docker-compose.test.yml run --rm db-update-test
docker exec ubc-test-runner /app/.venv/bin/python -m pytest tests -q
```

- **unit** (`app/tests/unit/`): валидаторы, схемы, настройки (`AppSettingsService`),
  токены, пароли, PDF, генераторы времени (часы 00–23, минуты по `minute_step`),
  тексты `RuCalendar`, роутинг динамического диалога (`process_and_go_next`,
  `go_back`, `_after_phone`, TIME → `input_time_hour`);
- **integration** (`app/tests/integration/`): репозитории и API на реальной
  тестовой БД (auth, categories/objects/users/visitors/requests, request-fields
  и привязки к категории, settings, PDF, sessions/devices); фикстуры `visitor`
  (с `phone`), `field_text`/`field_time`, `category_with_fields`, `request_obj`
  (со значениями полей); TRUNCATE всех таблиц и flushdb redis после каждого теста;
- `pytest-timeout` (`timeout = 120` в `app/pyproject.toml`) — висящий тест
  прерывается по таймауту, прогон не зависает;
- текущий прогон: **218 passed** (89 unit + 129 integration), ~3 мин.
