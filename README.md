# Универсальный конструктор меню бота Telegram

Веб-админка + Telegram-бот для управления двухуровневым меню: **категории → объекты**.
Объект содержит наименование, краткое описание (HTML) и PDF с полным описанием,
который бот отправляет посетителю документом.

- **Админка (Nuxt 3 SPA)** — управление контентом, пользователями, заявками, настройками.
- **Бот (aiogram 3)** — регистрация посетителей (ФИО + согласие на обработку ПД),
  просмотр меню с пагинацией, получение PDF, создание/отмена заявок.
  Форма заявки строится динамически по настраиваемым полям категории
  (текст/число/дата/время/варианты).
- **Уведомления** — через RabbitMQ: админам о регистрациях, менеджерам о заявках,
  посетителям о смене статуса заявки.

## Роли

| Роль | Где | Возможности |
|---|---|---|
| **admin** | админка | пользователи, настройки, справочник полей заявки, категории/объекты (CRUD), просмотр всех заявок, бан посетителей, сессии/устройства |
| **manager** | админка | чтение своих категорий и объектов (прямые связи + назначенные категории), обработка заявок по ним (подтвердить/отклонить/выполнить), дашборд |
| **visitor** | бот | регистрация, меню, PDF, заявки |

## Технологии

- **Сервисы**: nginx, postgresql, pgbouncer, redis, rabbitmq (docker compose)
- **Backend**: Python 3.13, uv, FastAPI, dishka, SQLAlchemy async, Alembic, faststream, structlog, PyJWT, bcrypt, nh3 (санитизация HTML)
- **Bot**: aiogram 3 (FSM в Redis), aiogram-dialog (динамическая форма заявки), aiohttp (опционально SOCKS-прокси)
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
srv/nginx/              nginx.conf, templates/{loc,prod}, snippets, docker-entrypoint.d
docker-compose*.yml     srv / backend / frontend / nginx.{loc,prod} / единый файл
init-letsencrypt.sh     первичный выпуск сертификата Let's Encrypt (prod)
docs/
  design-plan.md        план разработки и прогресс
  architecture.md       итоговая архитектура (ER, API, потоки данных)
```

## Быстрый старт (docker)

```bash
cp .env.example .env    # заполнить секреты (пароли, BOT_TOKEN, BACKEND_JWT_SECRET)
docker compose up -d --build
```

Окружение задаёт `PROJECT_ENVIRONMENT` (`loc` | `prod`): `docker-compose.yml`
подключает `docker-compose.nginx.${PROJECT_ENVIRONMENT}.yml`.

- **loc** — 8 контейнеров: nginx (http :80, без SSL), frontend, backend, bot,
  postgres, pgbouncer, redis, rabbitmq;
- **prod** — 9 контейнеров: + certbot; nginx — :80 (ACME + редирект) и :443 (TLS).

- Админка: `http://universal-bot-constructor.loc/` (домен из `PROJECT_DOMAIN`, см. `/etc/hosts`)
- API: `http://…/api/v1/health`, Swagger: `http://…/api/docs`

### Администратор (после применения миграций)

```bash
# в docker (пароль запрашивается интерактивно)
docker compose run --rm backend python -m app.scripts.create_admin --username admin

# локально (из каталога app/)
PYTHONPATH=src POSTGRES_HOST=127.0.0.1 ../.venv/bin/python -m app.scripts.create_admin \
    --username admin [--password ...] [--role admin|manager]
```

Повторный запуск безопасен: существующий пользователь обновляется
(пароль, роль, `is_active`). Коды выхода: 0 — успех, 1 — неверный ввод, 2 — ошибка БД.

### SSL (prod)

```bash
# .env: PROJECT_ENVIRONMENT=prod, PROJECT_URL_SCHEME=https, PROJECT_DOMAIN, CERTBOT_EMAIL
mkdir -p /data/universal-bot-constructor/certbot/{conf,www}   # ${CERTBOT_DATA_DIR}
docker compose up -d --build postgres pgbouncer redis rabbitmq backend bot frontend
./init-letsencrypt.sh            # --staging — тестовый CA, --force — перевыпуск
```

Продление автоматическое: certbot — `certbot renew` каждые 12 ч, nginx —
`nginx -s reload` каждые 6 ч (`srv/nginx/docker-entrypoint.d/40-reload-certs.sh`).

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
Основные группы: `PROJECT_*`, `CERTBOT_*` (prod), `POSTGRES_*`, `REDIS_*`, `RABBITMQ_*`, `BACKEND_*`
(JWT-секрет, каталог PDF), `CONSUMER_*` (очереди и routing keys уведомлений),
`BOT_*` (токен, прокси, webhook). Секреты в git не попадают.

## Тесты

```bash
# инфраструктура + test-runner (тестовая БД и очереди из .env.test)
docker compose -f docker-compose.srv.yml up -d
docker compose --env-file .env.test -f docker-compose.test.yml up -d test-runner
docker compose --env-file .env.test -f docker-compose.test.yml run --rm db-update-test

# полный прогон (unit + integration, ~3 мин)
docker exec ubc-test-runner sh -c "cd /app && python -m pytest tests/unit tests/integration -q"
```

## Документация

- [docs/architecture.md](docs/architecture.md) — архитектура, ER-модель, API-контракты, потоки данных
- [docs/design-plan.md](docs/design-plan.md) — план разработки и прогресс по шагам
