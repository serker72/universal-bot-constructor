# Архитектура системы «Универсальный конструктор меню бота Telegram»

> Итоговый документ проектирования (шаг 8). План разработки — `docs/design-plan.md`.

---

## 1. Обзор

Приложение управляет двухуровневым меню Telegram-бота: **категории → объекты**
(объект: категория, наименование, краткое описание HTML/Markdown, PDF с полным
описанием). Контент и пользователи управляются через веб-админку; посетители
работают с ботом: регистрация (ФИО + согласие на обработку ПД), просмотр меню,
получение PDF, создание и отмена заявок. Менеджеры обрабатывают заявки по своим
объектам в админке.

### Роли

| Роль | Где | Права |
|---|---|---|
| **admin** | frontend | пользователи, настройки, контент (категории/объекты), просмотр всех заявок (без обработки), бан посетителей, сессии/устройства |
| **manager** | frontend | свои объекты (связь объект↔менеджер), обработка заявок по ним |
| **visitor** | bot | регистрация, меню, PDF, заявки |

### Стек

- **services**: nginx, postgresql, pgbouncer, redis, rabbitmq (docker compose)
- **backend**: Python 3.13, uv, FastAPI, dishka, SQLAlchemy async, asyncpg,
  Alembic, faststream (RabbitMQ), structlog, PyJWT, bcrypt
- **bot**: aiogram 3 (FSM в Redis), aiohttp-сессия (SOCKS-прокси опционально)
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
bot/                aiogram: handlers/, keyboards.py (CallbackData), services.py, notifications.py
db/                 движок, фабрика сессий (commit при успехе / rollback при ошибке)
```

DI-скоупы dishka: **APP** (engine, redis, broker, Bot, EventPublisher, PdfService),
**REQUEST** (сессия БД, репозитории, AuthService, BotService). Сессия БД на запрос:
`commit` при успехе, `rollback` при исключении.

---

## 3. ER-модель

```
users ──┬──< object_managers >── objects ──> categories
        │                           │
        ├──< devices ──< sessions   │
        │                           │
        │              requests >───┘
        │                 │
        └── (telegram_id) visitors ──< requests

settings (key/value, отдельная таблица)
```

| Таблица | Ключевые поля | Назначение |
|---|---|---|
| **users** | id, username (unique), password_hash (bcrypt), role (admin/manager), telegram_id (nullable), is_active | персонал админки; telegram_id — для уведомлений |
| **categories** | id, name, sort_order, is_active | уровень 1 меню |
| **objects** | id, category_id FK, name, short_description, pdf_path, sort_order, is_active | уровень 2 меню; pdf_path — относительный путь в PDF-каталоге |
| **object_managers** | object_id FK, user_id FK, PK(object_id, user_id) | какие менеджеры обслуживают объект |
| **visitors** | id, telegram_id (unique), full_name, consent_given, consent_at, is_blocked, blocked_at | посетители бота |
| **requests** | id, visitor_id FK, object_id FK, phone, comment (nullable), status (enum), confirmed_at (nullable) | заявки; статусы: `new → approved → completed`, `new → rejected`, `new/approved → cancelled_by_customer` |
| **devices** | id, user_id FK, device_id (thumbmarkjs), user_agent, last_seen_at | устройства входа |
| **sessions** | id, device_id FK, user_id FK, refresh_token_jti, is_active, revoked_at | refresh-сессии (ротация, отзыв) |
| **settings** | key (PK), value | page_size (10), cancel_interval_hours (24), welcome_text, consent_text |

Миграции: `app/alembic/versions/` (9 миграций, async-движок). Запуск — см. §7.

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
| `GET/POST/PATCH/DELETE /categories[/{id}]` | admin | CRUD категорий (+sort_order, is_active) |
| `GET/POST/PATCH/DELETE /objects[/{id}]` | admin | CRUD объектов |
| `PUT /objects/{id}/managers` | admin | список менеджеров объекта |
| `PUT /objects/{id}/pdf` | admin | загрузка PDF (multipart, только application/pdf, ≤20 МБ) |
| `GET /objects/{id}/pdf` | auth | отдача PDF (inline, открытие в новой вкладке) |
| `GET/POST/PATCH/DELETE /users[/{id}]` | admin | CRUD персонала (защита последнего admin, запрет самоудаления) |
| `GET /visitors`, `POST /visitors/{id}/block`, `/unblock` | admin | посетители: поиск/фильтры, бан/разбан |
| `GET /requests` | admin/manager | список; менеджер — только по своим объектам; фильтры статус/объект/дата |
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
  объекта (описание, «Получить PDF» → документ Telegram, «Создать заявку»).
- **Заявка**: телефон → необязательный комментарий → статус `new` →
  уведомление менеджерам объекта.
- **Мои заявки**: список с пагинацией, статусы, отмена: `new` — всегда,
  `approved` — в пределах `cancel_interval_hours` от `confirmed_at`.
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
| `bot.notify.request.created` | bot (создание заявки) | менеджеры объекта |
| `bot.notify.request.cancelled` | bot (отмена посетителем) | менеджеры объекта |
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
посетитель: бот «Создать заявку» → телефон+комментарий → requests (new)
        → publish bot.notify.request.created → менеджерам объекта
менеджер:  frontend POST /requests/{id}/status (approved/rejected/completed)
        → БД → publish bot.notify.request.status → посетителю
посетитель: отмена (new всегда; approved в пределах cancel_interval_hours)
        → статус cancelled_by_customer → publish bot.notify.request.cancelled
        → менеджерам объекта
```

---

## 7. Запуск и эксплуатация

### Полный стек (docker)

```bash
cp .env.example .env          # заполнить секреты
docker compose up -d --build  # 8 контейнеров: nginx, frontend, backend, bot,
                              # postgres, pgbouncer, redis, rabbitmq
```

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
  FNV-1a-хеш для HTTP-разработки.
