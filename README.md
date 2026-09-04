# Универсальный конструктор меню бота Telegram

Веб-админка + Telegram-бот для управления двухуровневым меню: **категории → объекты**.
Объект содержит наименование, краткое описание (HTML/Markdown) и PDF с полным описанием,
который бот отправляет посетителю документом.

- **Админка (Nuxt 3 SPA)** — управление контентом, пользователями, заявками, настройками.
- **Бот (aiogram 3)** — регистрация посетителей (ФИО + согласие на обработку ПД),
  просмотр меню с пагинацией, получение PDF, создание/отмена заявок.
- **Уведомления** — через RabbitMQ: админам о регистрациях, менеджерам о заявках,
  посетителям о смене статуса заявки.

## Роли

| Роль | Где | Возможности |
|---|---|---|
| **admin** | админка | пользователи, настройки, категории/объекты, просмотр всех заявок, бан посетителей, сессии/устройства |
| **manager** | админка | свои объекты, обработка заявок по ним (подтвердить/отклонить/выполнить) |
| **visitor** | бот | регистрация, меню, PDF, заявки |

## Технологии

- **Сервисы**: nginx, postgresql, pgbouncer, redis, rabbitmq (docker compose)
- **Backend**: Python 3.13, uv, FastAPI, dishka, SQLAlchemy async, Alembic, faststream, structlog, PyJWT, bcrypt
- **Bot**: aiogram 3 (FSM в Redis), aiohttp (опционально SOCKS-прокси)
- **Frontend**: Nuxt 3, TailwindCSS, thumbmarkjs
- **Авторизация**: JWT access+refresh в httpOnly cookies, сессии на устройства, blacklist в Redis

## Структура проекта

```
app/                    backend + bot (один образ)
  src/app/
    api/                FastAPI: роутеры, схемы, health
    bot/                aiogram: хендлеры, клавиатуры, сервис, уведомления
    services/           бизнес-логика (auth, tokens, pdf, events)
    repository/         SQLAlchemy-репозитории
    domain/models/      ORM-модели
    di/                 провайдеры dishka
    config/             pydantic-settings (префиксы POSTGRES_/BOT_/CONSUMER_ …)
    db/                 движок и сессии
  alembic/              миграции
frontend/               админка (Nuxt 3 + Tailwind)
srv/nginx/              конфиги reverse proxy
docker-compose*.yml     srv / backend / frontend / единый файл
docs/
  design-plan.md        план разработки и прогресс
  architecture.md       итоговая архитектура (ER, API, потоки данных)
```

## Быстрый старт (docker)

```bash
cp .env.example .env    # заполнить секреты (пароли, BOT_TOKEN, BACKEND_JWT_SECRET)
docker compose up -d --build
```

Поднимаются 8 контейнеров: nginx, frontend, backend, bot, postgres, pgbouncer, redis, rabbitmq.

- Админка: `http://universal-bot-constructor.loc/` (домен из `PROJECT_DOMAIN`, см. `/etc/hosts`)
- API: `http://…/api/v1/health`, Swagger: `http://…/api/docs`
- Первый admin создаётся скриптом после применения миграций.

### Миграции

```bash
# локально (из корня проекта)
PYTHONPATH=app/src POSTGRES_HOST=127.0.0.1 .venv/bin/alembic -c app/alembic.ini upgrade head

# новая миграция (из каталога app/)
PYTHONPATH=../app/src POSTGRES_HOST=127.0.0.1 ../.venv/bin/alembic revision -m "message"

# через docker
docker compose -f docker-compose.dbupdate.yml run --rm db-update
```

## Локальная разработка

```bash
# инфраструктура (без приложений)
docker compose -f docker-compose.srv.yml up -d

# backend (корневой .venv)
uvicorn src.app.api.main:app --reload

# bot
python -m src.app.bot.main              # long-polling (dev) / webhook (prod)

# frontend
cd frontend && npm install && npm run dev
```

## Конфигурация

Все переменные — в `.env` (шаблон: `.env.example`), читаются pydantic-settings.
Основные группы: `PROJECT_*`, `POSTGRES_*`, `REDIS_*`, `RABBITMQ_*`, `BACKEND_*`
(JWT-секрет, каталог PDF), `CONSUMER_*` (очереди и routing keys уведомлений),
`BOT_*` (токен, прокси, webhook). Секреты в git не попадают.

## Документация

- [docs/architecture.md](docs/architecture.md) — архитектура, ER-модель, API-контракты, потоки данных
- [docs/design-plan.md](docs/design-plan.md) — план разработки и прогресс по шагам
