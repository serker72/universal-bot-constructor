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

## Требования к серверу

- **ОС**: Linux с ядром ≥ 5.x (Ubuntu 22.04/24.04 LTS или аналог), systemd;
- **ПО**: Docker Engine ≥ 24 с плагином `docker compose` v2 (только `docker
  compose` — отдельный `docker-compose` v1 не требуется), git;
- **Ресурсы (минимум)**: 2 CPU / 4 GB RAM / 20 GB диск (образы + БД + PDF-хранилище);
- **Сеть**: исходящие соединения к Docker Hub, PyPI/npm (сборка образов) и
  api.telegram.org; входящие :80 и :443 (prod — для Let's Encrypt HTTP-01 и
  доступа к админке; :80 обязателен даже при https);
- **Домен**: для prod — A-запись домена указывает на IP сервера (проверить до
  выпуска сертификата); для loc — имя хоста прописывается в `/etc/hosts`.

## CPU (воркеры backend)

Число воркеров uvicorn должно соответствовать количеству доступных CPU-ядер.
Количество ядер на сервере:

```bash
cat /proc/cpuinfo | grep 'processor' | wc -l
```

В `.env` (prod) установить:

```bash
BACKEND_WORKER_COUNT=<количество доступных CPU>
BACKEND_CONTAINER_COMMAND="--workers ${BACKEND_WORKER_COUNT}"
```

`--reload` (значение для разработки) в prod не использовать.

## Быстрый старт (docker)

### 1. Развертывание кода

Код проекта размещается в `/opt/universal-bot-constructor`:

```bash
git clone <repo-url> /opt/universal-bot-constructor
cd /opt/universal-bot-constructor
```

Либо извлечение архива в `/opt` с переименованием каталога в `universal-bot-constructor`.

### 2. Конфигурация `.env`

```bash
cp .env.example .env
```

- `PROJECT_DATA_DIR` — каталог данных на хосте (по умолчанию
  `/opt/universal-bot-constructor-data`);
- `BOT_TOKEN` — токен Telegram-бота: получить у [@BotFather](https://t.me/BotFather)
  (`/newbot` → имя → username) и вставить в `.env`; для webhook-режима в
  BotFather privacy mode можно оставить по умолчанию — команды задаются через `/setcommands`;
- заполнить секреты: пароли `POSTGRES_*`, `REDIS_*`, `RABBITMQ_*`, `BOT_TOKEN`,
  `BACKEND_JWT_SECRET` (для prod — чек-лист `.env` ниже).

### 3. Каталоги данных

Каталоги хоста монтируются в контейнеры (БД, redis, rabbitmq, pdf, backups,
certbot) — все выводятся из `PROJECT_DATA_DIR`:

```bash
mkdir -p /opt/universal-bot-constructor-data/{backups,certbot,db,pdf,rabbitmq,redis}
mkdir -p /opt/universal-bot-constructor-data/certbot/{conf,www}
```

### 3.1. Резервные копии PostgreSQL (сервис db-backup)

Сервис `db-backup` (`docker-compose.srv.yml`, образ `postgres:16.14-alpine`,
`srv/db-backup/entrypoint.sh`) поднимается вместе с инфраструктурой и ходит в
`postgres` напрямую (не через pgbouncer — дамп это длинная сессия). Выполняет
`pg_dump -Fc` (сжатый custom-формат, выборочное восстановление через
`pg_restore`) и пишет дампы в хостовый `POSTGRES_BACKUPS_DIR` — тот же том,
что примонтирован в `postgres`.

| Переменная `.env` | Назначение |
|---|---|
| `POSTGRES_BACKUP_AT` | время ежедневного дампа `ЧЧ:ММ` по UTC (часовой пояс контейнера) |
| `POSTGRES_BACKUP_KEEP` | сколько последних дампов хранить на каждую БД |
| `POSTGRES_BACKUP_DATABASES` | список БД через пробел (по умолчанию — `POSTGRES_DB`) |

Имена файлов — `<база>_ГГГГ-ММ-ДД_ЧЧММ.dump` (сортировка = хронология); лишние
дампы удаляются после успешного дампа, при сбое дамп не пишется и ротация не
выполняется.

```bash
# журнал сервиса (старт, время и размер каждого дампа, сбои)
docker compose logs -f db-backup

# состояние хранилища дампов на хосте
ls -lh "$POSTGRES_BACKUPS_DIR"

# восстановление из custom-дампа (БД должна существовать)
docker compose exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  /var/lib/postgresql/backups/<база>_<дата>_<время>.dump
```

### 4. Запуск контейнеров — один из сценариев

Окружение задаёт `PROJECT_ENVIRONMENT` (`loc` | `prod`): `docker-compose.yml`
подключает `docker-compose.nginx.${PROJECT_ENVIRONMENT}.yml`.

#### Сценарий loc (http, по умолчанию)

```bash
docker compose up -d --build   # все контейнеры за один запуск
```

- **loc** — 9 контейнеров: nginx (http :80, без SSL), frontend, backend, bot,
  postgres, pgbouncer, redis, rabbitmq, db-backup (ежедневные дампы, см. ниже);
- Админка: `http://universal-bot-constructor.loc/` (домен из `PROJECT_DOMAIN`, см. `/etc/hosts`)
- API: `http://…/api/v1/health`, Swagger: `http://…/api/docs`

#### Сценарий prod (https)

nginx (prod) не стартует без файлов сертификата, а certbot не пройдёт HTTP-01
без работающего nginx, поэтому сначала поднимается всё, кроме nginx и certbot —
их запускает `init-letsencrypt.sh` (это НЕ повторный запуск из loc-сценария):

```bash
# .env: PROJECT_ENVIRONMENT=prod, PROJECT_URL_SCHEME=https, PROJECT_DOMAIN, CERTBOT_EMAIL
docker compose up -d --build postgres pgbouncer redis rabbitmq backend bot frontend
./init-letsencrypt.sh --staging  # 1) проверка на тестовом CA (без лимитов)
./init-letsencrypt.sh            # 2) боевой сертификат (staging заменяется автоматически)
# --force — принудительный перевыпуск
```

- **prod** — 9 контейнеров: + certbot; nginx — :80 (ACME + редирект) и :443 (TLS).

Продление автоматическое: certbot — `certbot renew` каждые 12 ч, nginx —
`nginx -s reload` каждые 6 ч (`srv/nginx/docker-entrypoint.d/40-reload-certs.sh`).
HSTS — `NGINX_STRICT_TRANSPORT_SECURITY_MAX_AGE=86400` (24 ч) на период ввода prod;
после стабилизации — увеличить до `31536000` в `.env` (без правки шаблона) и
пересоздать контейнер nginx (envsubst шаблонов выполняется при старте контейнера):

```bash
docker compose up -d --force-recreate nginx
```

### 5. Общие шаги для loc | prod

#### Миграции (после запуска контейнеров)

```bash
# через docker
docker compose -f docker-compose.dbupdate.yml run --rm db-update

# локально (из корня проекта)
PYTHONPATH=app/src POSTGRES_HOST=127.0.0.1 .venv/bin/alembic -c app/alembic.ini upgrade head

# новая миграция (из каталога app/)
PYTHONPATH=../app/src POSTGRES_HOST=127.0.0.1 ../.venv/bin/alembic revision -m "message"
```

#### Администратор (после применения миграций)

```bash
# в docker (пароль запрашивается интерактивно)
docker compose run --rm backend python -m app.scripts.create_admin --username admin

# локально (из каталога app/)
PYTHONPATH=src POSTGRES_HOST=127.0.0.1 ../.venv/bin/python -m app.scripts.create_admin \
    --username admin [--password ...] [--role admin|manager]
```

Повторный запуск безопасен: существующий пользователь обновляется
(пароль, роль, `is_active`). Коды выхода: 0 — успех, 1 — неверный ввод, 2 — ошибка БД.

### 6. Проверка после установки

```bash
docker compose ps                        # все контейнеры Up/healthy
docker compose logs --tail=50 backend    # без ошибок, "Application startup complete"
docker compose logs --tail=50 bot        # бот подключился (polling/webhook)
curl -fsS http://127.0.0.1/api/v1/health          # liveness
curl -fsS http://127.0.0.1/api/v1/health/ready    # readiness (БД доступна)
```

- открыть админку (`http://…` / `https://…`), войти под созданным администратором;
- написать боту в Telegram — должна прийти приветственная регистрация;
- для prod: `curl -I https://<домен>/` — `308/301` редирект с http и валидный TLS.

### Штатные операции

```bash
# логи сервиса (logs / logs -f)
docker compose logs -f backend bot

# обновление кода (то же пересоздаёт образы, тома данных не трогаются)
git pull && docker compose up -d --build

# остановка (данные сохраняются в PROJECT_DATA_DIR)
docker compose down

# бэкап БД — автоматический: сервис db-backup (см. п. 3.1). Ручной снимок
# перед миграцией схемы:
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup.sql.gz
```

### Чек-лист `.env` для prod

| Переменная | Значение |
|---|---|
| `PROJECT_ENVIRONMENT` | `prod` (допустимы только `loc` / `prod` — иначе ошибка старта) |
| `PROJECT_URL_SCHEME` / `PROJECT_DOMAIN` | `https` / боевой домен (DNS → сервер) |
| `CERTBOT_EMAIL` | реальный e-mail (не `change_me`) |
| `CORS_ORIGINS` | `["${PROJECT_URL_SCHEME}://${PROJECT_DOMAIN}"]` |
| `SQLALCHEMY_DEBUG` | `False` (иначе SQL с параметрами — в логе) |
| `BACKEND_JWT_SECRET` | `openssl rand -base64 64 \| tr -d '\n'` (≥ 32 байт) |
| `BACKEND_WORKER_COUNT` | количество доступных CPU (см. «CPU (воркеры backend)») |
| `BACKEND_CONTAINER_COMMAND` | `--workers ${BACKEND_WORKER_COUNT}` (не `--reload`) |
| `BOT_WEBHOOK_BASE_URL` | `"${PROJECT_URL_SCHEME}://${PROJECT_DOMAIN}"` (пусто — long-polling) |
| `BOT_WEBHOOK_SECRET` | `openssl rand -hex 32` — обязателен при webhook, формат `A-Z a-z 0-9 _ -` |
| `NGINX_STRICT_TRANSPORT_SECURITY_MAX_AGE` | `86400` (24 ч) на период ввода prod, после стабилизации — `31536000` |
| `POSTGRES_BACKUP_AT` | время ежедневного дампа `ЧЧ:ММ` по UTC (например `03:15`) |
| `POSTGRES_BACKUP_KEEP` | число хранимых дампов на БД (например `7`) |
| `POSTGRES_*`, `REDIS_*`, `RABBITMQ_*` пароли | сгенерированные, не из примера |

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
